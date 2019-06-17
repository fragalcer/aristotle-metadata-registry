from typing import Any, List, Dict, Optional, Union, AnyStr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files import File
from django.core.files.storage import get_storage_class
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.mail.message import EmailMessage
from django.db.models.query import QuerySet
from django.http.request import QueryDict
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from hashlib import sha256
import pickle
import pypandoc

from aristotle_mdr.contrib.help.models import ConceptHelp
from aristotle_mdr import models as MDR
from aristotle_mdr.utils import fetch_aristotle_settings, get_model_label, format_seconds
from aristotle_mdr.utils.utils import get_download_template_path_for_item

import logging
logger = logging.getLogger(__name__)


class Downloader:
    """
    Base class used by all downloaders
    Subclasses must override the create_file method

    Required class properties:

    * description: a description of the downloader type
    * download_type: the extension or name of the download to support
    * icon_class: the font-awesome class
    * metadata_register: can be one of:

      * a dictionary with keys corresponding to django app labels and values as lists of models within that app the downloader supports
      * the string "__all__" indicating the downloader supports all metadata types
      * the string "__template__" indicating the downloader supports any metadata type with a matching download template
    """
    metadata_register: Union[Dict[str, List], str] = '__all__'
    # Font awsome icon to use
    icon_class: str = 'fa-file-text-o'
    description: str = ''
    filename: str = 'download'
    allow_wrapper_pages: bool = False  # Whether to allow a front and back page
    # A unique identifier for the downloader (used in url and passed to task)
    download_type: str = ''
    # Used to discover templates
    template_type: str = ''
    file_extension: str = ''
    requires_pandoc: bool = False
    # Download label (displayed to user)
    label: str = ''
    # Mime type used when sending file in an email
    mime_type: str = ''

    default_options = {
        'include_supporting': False,
        'include_related': False,
        'subclasses': None,
        'front_page': None,
        'back_page': None,
        'email_copy': False,
        'registration_status': None,
        'registration_authority': None,
    }

    def __init__(self, item_ids: List[int], user_id: Optional[int], options: Dict[str, Any] = {}, override_bulk: bool = False):
        self.item_ids = item_ids
        self.error = False

        if user_id is not None:
            self.user = get_user_model().objects.prefetch_related('profile').get(id=user_id)
        else:
            self.user = AnonymousUser()

        self.items = MDR._concept.objects.filter(id__in=item_ids).visible(self.user).select_subclasses()

        # Do len here since we are going to evaluate it later anyways
        self.numitems = len(self.items)
        self.bulk = (self.numitems > 1) or override_bulk

        if self.numitems == 0:
            raise PermissionDenied('User does not have permission to view any items')

        # Shallow copy of options
        self.options = self.default_options.copy()
        self.options.update(options)

    def create_file(self) -> File:
        """
        Create the file object, should be overwitten by subclasses
        See below for examples
        """
        raise NotImplementedError

    def get_storage(self, media=False):
        """Gets a storage class object (use media to get default media class instead of dl class)"""
        if settings.DOWNLOADS_STORAGE is not None and not media:
            storage_class = import_string(settings.DOWNLOADS_STORAGE)
        else:
            storage_class = get_storage_class()
        return storage_class()

    @property
    def has_wrap_pages(self):
        return (self.options['front_page'] is not None or self.options['back_page'] is not None)

    def get_wrap_pages(self) -> List:
        if not self.allow_wrapper_pages:
            return [None, None]

        storage = self.get_storage(media=True)
        pages = []
        for page_name in ['front_page', 'back_page']:
            page_path = self.options[page_name]
            if page_path is not None:
                with storage.open(page_path) as page_file:
                    pages.append(page_file.read())
            else:
                pages.append(None)

        return pages

    def get_filepath(self):
        if self.user.is_authenticated:
            userpart = str(self.user.id)
        else:
            userpart = 'anon'

        arghash = sha256()
        arghash.update(pickle.dumps(self.item_ids))
        arghash.update(pickle.dumps(self.options))

        fname = '/'.join([userpart, arghash.hexdigest(), self.filename])
        if self.file_extension:
            return '.'.join([fname, self.file_extension])

        return fname

    def retrieve_file(self, filename: str) -> Optional[str]:
        """Use default storage class to retrieve file if it exists"""
        storage = self.get_storage()
        if storage.exists(filename):
            file_modified = storage.get_modified_time(filename)
            for item in self.items:
                # If one of the items has been modified after the file
                if item.modified > file_modified:
                    storage.delete(filename)
                    return None
            # If the file was modified after the items
            return storage.url(filename)
        return None

    def store_file(self, filename: str, content: File) -> str:
        """Use default storage class to store file"""
        storage = self.get_storage()
        # Filename can change if a file already exists
        # (wont happen unless caching is off)
        final_fname = storage.save(filename, content)
        return storage.url(final_fname)

    def email_file(self, f: File, size: int, url: str):
        template_name = 'aristotle_mdr/email/download.html'
        context: Dict[str, Union[str, bool]] = {
            'item_names': ', '.join([i.name for i in self.items]),
            'download_url': url
        }

        # Send email with a link to the file and link to regenerate
        storage = self.get_storage()
        if hasattr(storage, 'querystring_expire'):
            expire_seconds = storage.querystring_expire
            context['expire_time'] = format_seconds(expire_seconds)
        # Build url to regenerate download
        query = QueryDict(mutable=True)
        query.setlist('items', self.item_ids)
        regenerate_url = '{url}?{qstring}'.format(
            url=reverse('aristotle:download_options', args=[self.download_type]),
            qstring=query.urlencode()
        )
        # Update context
        context.update({'attached': False, 'regenerate_url': regenerate_url})

        email = EmailMessage(
            'Aristotle Download',
            render_to_string(template_name, context),
            to=[self.user.email],
        )
        email.content_subtype = 'html'  # Sets the mime type of the body to text/html
        email.send(fail_silently=True)

    def download(self) -> str:
        """Get the url for this downloads file, creating it if neccesary"""
        filepath = self.get_filepath()

        if settings.DOWNLOAD_CACHING:
            url = self.retrieve_file(filepath)
            if url is not None:
                return url

        fileobj = self.create_file()
        size = fileobj.size  # Access size here while file is open

        url = self.store_file(filepath, fileobj)

        if self.options['email_copy']:
            self.email_file(fileobj, size, url)

        return url

    @classmethod
    def get_class_info(cls) -> Dict[str, Any]:
        """Used as context instead of passing classes to templates"""
        return {
            'icon_class': cls.icon_class,
            'label': cls.label,
            'download_type': cls.download_type,
            'description': cls.description
        }


class HTMLDownloader(Downloader):
    """
    Generates a html download
    This is subclassed for other formats that are generated from html
    such as the pdf downloader. But can be enabled for testing purposes
    """

    download_type = 'html'
    template_type = 'html'
    file_extension = 'html'
    label = 'HTML'
    mime_type = 'text/html'
    metadata_register = '__all__'
    description = 'Download as html (used for debugging)'

    bulk_download_template = 'aristotle_mdr/downloads/html/bulk_download.html'

    def get_base_download_context(self) -> Dict[str, Any]:
        # page size for the pdf
        aristotle_settings = fetch_aristotle_settings()
        page_size = aristotle_settings.get('PDF_PAGE_SIZE', 'A4')

        context = {
            'infobox_identifier_name': aristotle_settings.get('INFOBOX_IDENTIFIER_NAME', _("Item ID")),
            'user': self.user,
            'page_size': page_size,
            'options': self.options,
            'config': aristotle_settings,
            "export_date": now(),
        }
        return context

    def get_download_context(self) -> Dict[str, Any]:
        """
        Return context for single item download
        """
        context = self.get_base_download_context()

        # This will raise an exception if the list is empty, but that's ok
        item = self.items[0]
        if self.options['include_supporting']:
            sub_items = self.get_sub_items_dict()
        else:
            sub_items = {}

        context.update({
            'title': item.name,
            'item': item,
            'subitems': sub_items,
            'tableOfContents': len(sub_items) > 0,
        })
        return context

    def _add_to_sub_items(self, items_dict, item):
        item_class = type(item)

        label = get_model_label(item_class)

        if label not in items_dict:
            model_help = ConceptHelp.objects.filter(
                app_label=item_class._meta.app_label,
                concept_type=item_class._meta.model_name
            ).first()

            items_dict[label] = {
                'items': [],
                'verbose_name': item_class.get_verbose_name(),
                'verbose_name_plural': item_class.get_verbose_name_plural(),
                'help': model_help
            }

        items_dict[label]['items'].append(item)

    def get_sub_items_dict(self, include_root=False) -> Dict[str, Dict[str, Any]]:
        """Function that populates the supporting items in the template. Only populates
         the """
        items: Dict[str, Dict[str, Any]] = {}

        # Get all items using above method to create dict
        for item in self.items:
            # include_root includes the selected items in the dict
            if include_root:
                self._add_to_sub_items(items, item)

            registration_authority_id = self.options['registration_authority']
            state = self.options['registration_status']

            for download_items in item.get_download_items():

                if isinstance(download_items, QuerySet):
                    # It's a queryset with multiple items

                    if registration_authority_id is not None:
                        download_items = download_items.filter(statuses__registrationAuthority=registration_authority_id)

                    if state is not None:
                        download_items = download_items.filter(statuses__state=state)

                    sub_list = list(download_items.visible(self.user))

                else:
                    raise AssertionError("Must be a QuerySet")

                for sub_item in sub_list:
                    # Can be none for components
                    if sub_item is not None:
                        self._add_to_sub_items(items, sub_item)

        # Sort the items lists by name
        for label, data in items.items():
            data['items'].sort(key=lambda item: item.name)

        return items

    def get_bulk_download_context(self) -> Dict[str, Any]:
        """
        Return context for bulk download
        """
        context = self.get_base_download_context()

        _list = "<li>" + "</li><li>".join([item.name for item in self.items if item]) + "</li>"
        subtitle = mark_safe("Generated from the following metadata items:<ul>%s<ul>" % _list)

        # sub_items = self.get_sub_items_dict(include_root=True)
        if self.options['include_supporting']:
            sub_items = self.get_sub_items_dict()
        else:
            sub_items = {}

        context.update({
            'subtitle': subtitle,
            'tableOfContents': True,
            'items': self.items,
            'included_items': sub_items
        })
        return context

    def get_context(self) -> Dict[str, Any]:
        """
        Gets the template context
        Can be used by subclasses
        """
        if self.bulk:
            context = self.get_bulk_download_context()
        else:
            context = self.get_download_context()
        context.update({"is_bulk_download": self.bulk})

        return context

    def get_template(self) -> str:
        """
        Gets the template contex
        Can be used by subclasses
        """
        if self.bulk:
            return self.bulk_download_template
        else:
            # This will raise an exception if the list is empty, but thats ok
            item = self.items[0]
            # Template folder should be renamed to html
            return get_download_template_path_for_item(item, self.template_type)

    def get_html(self) -> bytes:
        """
        Gets the rendered html string
        Can be used by subclasses
        """
        template = self.get_template()
        context = self.get_context()
        safestring = render_to_string(template, context=context)
        return str(safestring).encode()

    def create_file(self):
        html = self.get_html()
        return ContentFile(html)


class PandocDownloader(HTMLDownloader):
    """
    Used as base class for downloader converting html to other
    formats via pandoc. Does not work as a downloader itself
    """

    requires_pandoc = True

    def convert_html(self, html) -> AnyStr:
        raise NotImplementedError

    def create_file(self):
        html = self.get_html()
        string = self.convert_html(html)
        return ContentFile(string)


class DocxDownloader(PandocDownloader):

    download_type = 'docx'
    file_extension = 'docx'
    label = 'Word'
    # Yep, the proper mime type for docx really is that long
    mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.template'
    metadata_register = '__all__'
    icon_class = 'fa-file-word-o'
    description = 'Download as word document'

    def convert_html(self, html):
        return pypandoc.convert_text(html, 'docx', format='html', return_bytes=True)


class ODTDownloader(PandocDownloader):

    download_type = 'odt'
    file_extension = 'odt'
    label = 'ODT'
    mime_type = 'application/vnd.oasis.opendocument.text'
    metadata_register = '__all__'
    icon_class = 'fa-file-word-o'
    description = 'Download as odt document'

    def convert_html(self, html):
        return pypandoc.convert_text(html, 'odt', format='html', return_bytes=True)


class MarkdownDownloader(PandocDownloader):

    download_type = 'md'
    file_extension = 'md'
    label = 'Markdown'
    mime_type = 'text/markdown'
    metadata_register = '__all__'
    description = 'Download as markdown'

    def convert_html(self, html):
        return pypandoc.convert_text(html, 'md', format='html')
