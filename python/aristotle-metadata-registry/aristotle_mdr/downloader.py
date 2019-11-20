from typing import Any, List, Dict, Optional, Union, AnyStr, Set

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files import File
from django.core.files.storage import get_storage_class
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.mail.message import EmailMessage
from django.db.models.query import QuerySet
from django.db.models import Q
from django.http.request import QueryDict
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from operator import attrgetter
from hashlib import sha256
from collections import defaultdict
import pickle
import pypandoc

from aristotle_mdr.contrib.help.models import ConceptHelp
from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.custom_fields.models import CustomValue
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
    # Fontawesome icon to use
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
        self.order_fields = ['name']

        if user_id is not None:
            self.user = get_user_model().objects.prefetch_related('profile').get(id=user_id)
        else:
            self.user = AnonymousUser()

        self.items = MDR._concept.objects.filter(id__in=item_ids).visible(self.user).select_subclasses().order_by(*self.order_fields)

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
        Create the file object, should be overwritten by subclasses
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
        """Get the url for this downloads file, creating it if necessary"""
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


class ItemList:
    """Class for storing items of one type along with model information (used in sub_dict below)"""

    def __init__(self, model_class, items: List = []):
        # Private properties
        self._cache: Dict = {}
        self._model_class = model_class
        self._items = {i.id: i for i in items}
        # Public properties
        self.app_label = self._model_class._meta.app_label
        self.model_name = self._model_class._meta.model_name
        self.verbose_name = self._model_class.get_verbose_name()
        self.verbose_name_plural = self._model_class.get_verbose_name_plural()

    @property
    def model_pluralized(self):
        """Get model name as plural if more than one"""
        if len(self) > 1:
            return self.verbose_name_plural
        return self.verbose_name

    @property
    def ids(self) -> List[int]:
        """List of item ids in list"""
        return [i.id for i in self._items.values()]

    @property
    def items(self):
        """Iterator of items"""
        return self._items.values()

    @property
    def help(self) -> Optional[ConceptHelp]:
        """
        Help object for the model (None if not found)
        This is cached so repeated calls are ok
        """
        if 'help' in self._cache:
            return self._cache['help']

        try:
            help_obj = ConceptHelp.objects.get(
                app_label=self.app_label,
                concept_type=self.model_name
            )
        except ConceptHelp.DoesNotExist:
            help_obj = None

        self._cache['help'] = help_obj
        return help_obj

    def has_item(self, iid):
        """Whether the list contins item with this id"""
        return iid in self._items

    def get_item(self, iid):
        """Get item by id"""
        return self._items[iid]

    def __getitem__(self, key):
        """Support indexing the itemlist to get an item"""
        return self.get_item(key)

    def add_item(self, item):
        """Add item to list"""
        self._items[item.id] = item

    def as_dict(self):
        """Return copy of internal dictionary"""
        return self._items.copy()

    def __len__(self):
        """Support len()"""
        return len(self._items)

    def sorted_items(self):
        """Items sorted by name"""
        items_list = list(self.items)
        return sorted(items_list, key=attrgetter('name'))


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

        aristotle_settings = fetch_aristotle_settings()

        context = {
            'infobox_identifier_name': aristotle_settings.get('INFOBOX_IDENTIFIER_NAME', _("Item ID")),
            'user': self.user,
            'options': self.options,
            'config': aristotle_settings,
            'export_date': now(),
        }
        context['CURRENT_CLIENT_BASE'] = getattr(settings, 'CURRENT_CLIENT_BASE', None)
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

        # Add tree if dss
        if 'aristotle_dse' in settings.INSTALLED_APPS:
            from aristotle_dse.models import DataSetSpecification, DSSClusterInclusion, DSSDEInclusion
            inclusion_orderer = {DSSClusterInclusion: 0, DSSDEInclusion: 1}
            if isinstance(item, DataSetSpecification):
                kwargs = self.prelim.get(item.id, None)
                if kwargs:
                    kwargs['objects'] = {}
                    # Reuse sub objects if already avaliable (saves a query)
                    if sub_items:
                        if 'aristotle_dse.datasetspecification' in sub_items:
                            kwargs['objects'].update(sub_items['aristotle_dse.datasetspecification'].as_dict())
                        if 'aristotle_dse.dataelement' in sub_items:
                            kwargs['objects'].update(sub_items['aristotle_mdr.dataelement'].as_dict())

                    dss_tree = item.get_cluster_tree(**kwargs)
                    context['tree'] = dss_tree

                    # A nice lambda to force ordering by inclusion type, then inclusion order
                    child_sorter = lambda node: (inclusion_orderer.get(node.relation_data.__class__, 999), node.relation_data.order)
                    context['tree_values'] = dss_tree.get_values(dss_tree.root, sort_by=child_sorter)

        context.update({
            'title': item.name,
            'item': item,
            'subitems': sub_items,
            'tableOfContents': len(sub_items) > 0,
        })
        return context

    def _add_to_sub_items(self, items_dict, item):
        """Adds an item to the sub items dict"""
        item_class = type(item)

        label = get_model_label(item_class)

        # Create a new item list if label not in dict
        if label not in items_dict:
            items_dict[label] = ItemList(item_class)

        # Add item to itemlist
        items_dict[label].add_item(item)

    def get_sub_items_dict(self, include_root=False) -> Dict[str, ItemList]:
        """Function that populates the supporting items in the template"""
        items: Dict[str, ItemList] = {}

        glossary_enabled = False
        if 'aristotle_glossary' in settings.INSTALLED_APPS:
            from aristotle_glossary.models import GlossaryItem
            glossary_items = GlossaryItem.objects.none()
            glossary_enabled = True

        # Get all items using above method to create dict
        for item in self.items:
            # include_root includes the selected items in the dict
            if include_root:
                self._add_to_sub_items(items, item)

            registration_authority_id = self.options['registration_authority']
            state = self.options['registration_status']

            # Fetch prelim values, use with get_download item if avaliable
            prelim = self.prelim.get(item.id, {})
            all_download_items = item.get_download_items(**prelim)

            for download_items in all_download_items:

                if isinstance(download_items, QuerySet):
                    # It's a queryset with multiple items

                    if registration_authority_id is not None:
                        download_items = download_items.filter(statuses__registrationAuthority=registration_authority_id)

                    if state is not None:
                        download_items = download_items.filter(statuses__state=state)

                    sub_query = download_items.visible(self.user)

                    # Prefetch all sub objects on a value domain
                    if sub_query.model == MDR.ValueDomain:
                        sub_query = sub_query.select_related(
                            'unit_of_measure', 'conceptual_domain', 'data_type'
                        ).prefetch_related(
                            'permissiblevalue_set', 'supplementaryvalue_set'
                        )

                    sub_list = list(sub_query)

                    if glossary_enabled:
                        glossary_items |= GlossaryItem.objects.filter(index__in=download_items)

                else:
                    raise AssertionError("Must be a QuerySet")

                for sub_item in sub_list:
                    # Can be none for components
                    if sub_item is not None:
                        self._add_to_sub_items(items, sub_item)

        if glossary_enabled:
            for sub_item in glossary_items.visible(self.user):
                # Can be none for components
                if sub_item is not None:
                    self._add_to_sub_items(items, sub_item)

        return items

    def get_bulk_download_context(self) -> Dict[str, Any]:
        """
        Return context for bulk download
        """
        context = self.get_base_download_context()

        if self.options['include_supporting']:
            sub_items = self.get_sub_items_dict()
        else:
            sub_items = {}

        context.update({
            'tableOfContents': True,
            'items': self.items,
            'supporting_items': sub_items
        })
        return context

    def get_preliminary_values(self) -> Dict:
        """Fetch prelim values for calculation of download items"""
        prelim = {}
        for item in self.items:
            if 'aristotle_dse' in settings.INSTALLED_APPS:
                from aristotle_dse.models import DataSetSpecification
                if isinstance(item, DataSetSpecification):
                    cluster_relations = item.get_all_clusters()
                    dss_ids = item.get_unique_ids(cluster_relations)
                    de_relations = item.get_de_relations(dss_ids)

                    prelim[item.id] = {
                        'cluster_relations': cluster_relations,
                        'de_relations': de_relations
                    }

        return prelim

    def qs_as_dict(self, qs, concept_field_name='concept') -> Dict[int, List]:
        """Get queryset as dict mapping ids to lists of objects"""
        concept_id_field_name = concept_field_name + '_id'
        object_dict: Dict = defaultdict(list)
        for o in qs:
            concept_id = getattr(o, concept_id_field_name)
            object_dict[concept_id].append(o)

        return object_dict

    def get_caches(self, context: Dict) -> Dict:
        # Build set of all items & subitem id's
        all_ids: Set = {i.id for i in self.items}

        if 'subitems' in context:
            subitems = context['subitems']
            # Add to all_ids
            for label, itemlist in subitems.items():
                for iid in itemlist.ids:
                    all_ids.add(iid)

        # Bulk lookup current status
        status_objs = MDR.Status.objects.filter(concept__in=all_ids).current().all()
        # Bulk lookup custom values (with non empty content)
        custom_values = CustomValue.objects.filter(
            concept__in=all_ids
        ).with_content().visible(self.user).select_related('field')

        context.update({
            'current_statuses': self.qs_as_dict(status_objs),
            'custom_values': self.qs_as_dict(custom_values)
        })
        return context

    def get_context(self) -> Dict[str, Any]:
        """
        Gets the template context
        Can be used by subclasses
        """
        self.prelim = self.get_preliminary_values()

        if self.bulk:
            context = self.get_bulk_download_context()
        else:
            context = self.get_download_context()

        context = self.get_caches(context)
        context.update({"is_bulk_download": self.bulk})

        return context

    def get_template(self) -> str:
        """
        Gets the template context
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
