from typing import List, Optional, Any, Union
from django.urls import reverse
from django.utils.html import format_html

from aristotle_mdr.templatetags.util_tags import bleach_filter
from aristotle_mdr.models import _concept


class VersionField:
    """
    Field for use in previous version display
    Template to render in helpers/version_field.html
    """

    empty_text: str = 'None'
    link: bool = False
    group: bool = False

    def __init__(self, fname: str, value, html=False):
        self.fname = fname
        self.value = str(value)
        self.html = html

    @property
    def is_link(self):
        return self.link

    @property
    def is_group(self):
        return self.group

    @property
    def is_html(self):
        return self.html

    @property
    def heading(self):
        return self.fname

    def __str__(self):
        raw = self.value

        if not raw:
            raw = self.empty_text

        if self.html:
            return bleach_filter(raw)  # Automatically bleach result if html
        return raw


class VersionLinkField(VersionField):
    """
    Version field that links to a concept
    """

    empty_text = 'None'
    perm_message = 'Linked to object you do not have permission to view'

    link = True
    group = False
    html = False

    def __init__(self, fname: str, identifier: Union[int, str, None], obj: Optional[Any]):
        """
        :param fname: Str: Name of the field.
        :param identifier: This class attribute represents the kind of identifier used in this LinkField.
        We use integers to represent ids, or strings type to represent uuids.
        :param obj: Metadata object linked to this VersionLinkField object
        """
        self.fname = fname
        self.identifier = identifier
        self.obj = obj
        self.is_concept = isinstance(obj, _concept)

    @property
    def url(self):
        if self.obj and self.is_concept:
            return reverse('aristotle:item', args=[self.obj.id])
        return ''

    @property
    def obj_name(self):
        if self.obj:
            if hasattr(self.obj, 'name'):
                return self.obj.name
            else:
                return str(self.obj)
        return ''

    def __str__(self):  # Get a nice name for object
        if self.identifier is not None:
            if self.obj:
                url = self.url
                if url:
                    return format_html(  # Build link dynamically
                        '<a href="{url}">{name}</a> <span class="text-danger">*</span>',
                        url=url,
                        name=self.obj_name
                    )
                else:
                    return self.obj_name  # Return plain name
            else:
                return self.perm_message  # If field is set but object is None no perm
        return self.empty_text  # Empty value if no id


class VersionGroupField(VersionField):
    """Field with groups of subfields (used for subserialized items)"""

    empty_text = 'Empty'
    link = False
    group = True
    html = False

    def __init__(self, fname: str, sub_fields: List[List[VersionField]]):
        self.fname = fname
        self.sub_fields = sub_fields

    @property
    def heading(self):
        if self.fname and self.fname[-1] != 's':  # Pluralize names for grouped field
            return self.fname + 's'
        return self.fname

    @property
    def headings(self) -> List[str]:
        headings = []
        if self.sub_fields:
            for field in self.sub_fields[0]:
                headings.append(field.heading)
        return headings

    def __str__(self):
        if len(self.sub_fields) > 0:
            return '{} items'.format(len(self.sub_fields))
        return self.empty_text


class VersionMultiLinkField(VersionField):
    """Field containing a group of link fields (used for reverse fk or m2m)"""

    empty_text = 'Empty'
    link = True
    group = False
    html = False

    def __init__(self, fname, sub_links: List[VersionLinkField]):
        self.fname = fname
        self.sub_links = sub_links

    def __str__(self):  # Get str of sub fields
        sub_strings = [str(f) for f in self.sub_links]
        result = ', '.join(sub_strings)

        if result:
            # Result can contain html links along with user data
            # so bleaching is required here
            return bleach_filter(result)

        return self.empty_text
