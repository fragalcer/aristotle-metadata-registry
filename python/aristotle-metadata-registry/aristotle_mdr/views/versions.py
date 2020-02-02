import json
import reversion
import diff_match_patch
import uuid
from django.db.models.query import QuerySet
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.views.generic.list import ListView
from django.views.generic import TemplateView
from django.db.models import Model, Field
from django.urls import reverse
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import get_object_or_404

from aristotle_mdr import models as MDR
from aristotle_mdr.perms import user_can_edit
from aristotle_mdr.constants import visibility_permission_choices as VISIBILITY_PERMISSION_CHOICES
from aristotle_mdr.constants import REVERSION_FORMATS
from aristotle_mdr.views.utils import SimpleItemGet
from aristotle_mdr.utils.utils import strip_tags, cloud_enabled
from aristotle_mdr.contrib.custom_fields.models import CustomValue
from aristotle_mdr.contrib.publishing.models import VersionPermissions
from aristotle_mdr.contrib.custom_fields.models import CustomField
from aristotle_mdr.utils.versions import VersionField, VersionLinkField, VersionGroupField, VersionMultiLinkField

from ckeditor_uploader.fields import RichTextUploadingField as RichTextField
from typing import Dict, List, Optional, Tuple, Any, Set

import logging

logger = logging.getLogger(__name__)

LookupDict = Dict[str, Dict[int, Any]]  # Type alias


class VersionsMixin:
    """
    Mixin providing helper functionality to views handling Versions data.
    """

    def user_can_view_version(self, user, metadata_item, version_permission: VersionPermissions) -> bool:
        """
        Determine whether or not user can view the specific version.
        :param user: User to determine user permissions from.
        :param metadata_item: Item to check user permissions.
        :param version_permission: Specific version to check user permissions.
        :return: Boolean
        """
        user_in_item_wg = metadata_item.workgroup and user in metadata_item.workgroup.member_list  # Apply workgroup permissions
        authenticated_user = not user.is_anonymous

        if user.is_superuser:  # Superusers can see everything
            return True

        if metadata_item.stewardship_organisation is None \
                and metadata_item.workgroup is None and metadata_item.submitter_id == user.id:
            # If you submitted the item and it has not been passed onto a workgroup or stewardship organisation
            return True

        if version_permission is None:
            if user_in_item_wg:
                return True
        else:
            visibility = int(version_permission.visibility)

            if visibility == VISIBILITY_PERMISSION_CHOICES.workgroup:
                if user_in_item_wg:
                    return True

            elif visibility == VISIBILITY_PERMISSION_CHOICES.auth:
                # Exclude anonymous users
                if authenticated_user:
                    return True
            else:
                # Visibility is public, don't exclude
                return True

        return False

    def get_concept_versions_for_user(self, concept, user) -> QuerySet:
        """
        Get versions and apply permission checking so that only versions that the user is allowed to see are
        shown.
        """

        versions = reversion.models.Version.objects.filter(object_id=concept.id)

        # Determine the viewing permissions of the users
        version_to_permission = VersionPermissions.objects.in_bulk(versions)
        for version in versions:
            if version.format == 'json':  # It's the old format
                serialized_data = json.loads(version.serialized_data)[0]
                if serialized_data['model'] != 'aristotle_mdr._concept':  # Only compare fields on the actual concept
                    versions = versions.exclude(id=version.id)

            if version.id in version_to_permission:
                version_permission = version_to_permission[version.id]
            else:
                version_permission = None
            if not self.user_can_view_version(user, concept, version_permission):
                versions = versions.exclude(pk=version.pk)

        versions = versions.order_by('-revision__date_created')
        return versions

    def is_model_field_html(self, field_name: str, model: Model) -> bool:
        try:
            field_obj = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return False
        return self.is_field_obj_html(field_obj)

    def is_field_obj_html(self, field: Field) -> bool:
        return issubclass(type(field), RichTextField)

    def get_html_custom_field_ids(self) -> Set[int]:
        ids_qs = CustomField.objects.filter(type='html').values_list('id', flat=True)
        return set(ids_qs)

    def get_model_from_foreign_key_field(self, parent_model: Model, field) -> Model:
        try:
            return parent_model._meta.get_field(field).related_model
        except FieldDoesNotExist:
            return parent_model._meta.get_field(self.clean_field_name(field)).related_model

    def clean_field_name(self, field: str) -> str:
        postfix = '_set'
        if field.endswith(postfix):
            return field[:-len(postfix)]
        return field

    def get_field(self, field_name: str, model) -> Field:
        try:
            field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            field = model._meta.get_field(self.clean_field_name(field_name))
        return field

    def get_field_or_none(self, field_name: str, model) -> Optional[Field]:
        try:
            field = self.get_field(field_name, model)
        except FieldDoesNotExist:
            field = None
        return field

    def get_user_friendly_field_name(self, field: str, model) -> str:
        # If the field ends with _set we want to remove it, so we can look it up in the _meta.
        field_obj = self.get_field(field, model)
        try:
            name = self.get_verbose_name(field_obj)
        except AttributeError:
            name = field
        return name

    def get_verbose_name(self, field: Field) -> str:
        name: str
        if field.is_relation:
            name = field.related_model._meta.verbose_name
        else:
            name = field.verbose_name

        if '_' in name:
            name = name.replace('_', ' ')
        return name.title()

    def remove_disallowed_custom_fields(self, user, serialized_data, concept) -> Dict:
        """
        Remove disallowed/deactivated custom fields from data structure.
        """
        allowed_custom_fields = CustomField.objects.get_allowed_fields(concept, user)
        allowed_ids = [custom_field.id for custom_field in allowed_custom_fields]

        if not ('customvalue_set' in serialized_data):
            return serialized_data

        custom_values = serialized_data['customvalue_set']
        serialized_custom_values = []
        for value in custom_values:
            if value['field'] in allowed_ids:
                serialized_custom_values.append(value)

        serialized_data['customvalue_set'] = serialized_custom_values

        return serialized_data

    def is_concept_fk(self, field):
        """
        Check whether field is a foreign key to a concept.
        """
        return field.many_to_one and issubclass(field.related_model, MDR._concept)

    def is_reference_doc_fk(self, field) -> bool:
        """
        Check whether field is a reference to a Reference Document.
        """
        if cloud_enabled():
            from aristotle_cloud.contrib.steward_extras.models import ReferenceBase
            if field.is_relation:
                return field.related_model == ReferenceBase
        return False

    def is_link_field(self, field) -> bool:
        """
        Check whether field is a foreign key to an item we want to display lookup value for.
        """
        if field.many_to_one:
            related = field.related_model
            return issubclass(related, MDR._concept) or related == CustomField
        return False


class ConceptVersionView(VersionsMixin, TemplateView):
    """
    Display the version of a concept at a particular point.
    """

    template_name = 'aristotle_mdr/concepts/managedContentVersion.html'
    version_arg = 'verid'
    # Top level fields to exclude
    excluded_fields = ['id', 'uuid', 'name', 'version', 'submitter', 'created', 'modified', 'serialized_model']
    # Excluded fields on subserialised items
    excluded_subfields = ['id', 'group']

    def dispatch(self, request, *args, **kwargs):
        self.version = self.get_version_object()
        self.item = self.version.object
        self.model = self.version.content_type.model_class()
        self.is_most_recent = self.is_this_version_the_most_recent()

        if not issubclass(self.model, MDR._concept):  # Check it's a concept version
            raise Http404

        try:  # Try to get version permission
            self.version_permission = VersionPermissions.objects.get(pk=self.version.pk)
        except VersionPermissions.DoesNotExist:
            self.version_permission = None

        if not self.user_can_view_version(self.request.user, self.item, self.version_permission):
            raise PermissionDenied  # Raise 403 (Forbidden) when user is not supposed to view this version.

        self.version_dict = self.get_version_data(self.version.serialized_data, self.item)  # Deserialize version data

        self.html_custom_field_ids: Set[int] = self.get_html_custom_field_ids()  # Fetch html custom field ids

        return super().dispatch(request, *args, **kwargs)

    def is_this_version_the_most_recent(self) -> bool:
        """
        Check if the version passed is actually the most recent version for this item.
        :return: Boolean
        """
        latest_version = reversion.models.Version.objects.filter(
            object_id=self.item.id, content_type=self.version.content_type
        ).latest('revision__date_created')
        return self.version == latest_version

    def get_version_object(self) -> reversion.models.Version:
        """
        Lookup version object.
        :return: Version object
        """
        return get_object_or_404(reversion.models.Version, id=self.kwargs[self.version_arg])

    def get_version_data(self, version_json: str, item: MDR._concept):
        """
        Deserialize and filter version data.
        """
        try:
            version_dict = json.loads(version_json)
        except json.JSONDecodeError:  # Handle bad serialized data
            raise Http404

        if type(version_dict) == list:
            # It's the old format
            version_dict = version_dict[0]['fields']

        return self.remove_disallowed_custom_fields(self.request.user, version_dict, item)

    def is_concept_multiple(self, field: Field):
        """
        Check whether a field is a _concept and is a Foreign Key to multiple concepts, such as OneToMany OR ManyToMany.
        :param field: Field to be inspected.
        :return: Boolean
        """
        return (field.many_to_many or field.one_to_many) and issubclass(field.related_model, MDR._concept)

    def get_field_data(self, version_data: Dict, model, exclude: List[str] = []) -> Dict:
        """
        Replace data with (field, data) tuples.
        """
        field_data = {}

        for name, data in version_data.items():
            if name not in exclude or not exclude:  # If field name isn't excluded or we are not excluding
                field = self.get_field_or_none(name, model)
                if field:
                    if type(data) == list and field.is_relation:  # If field is subserialized
                        sub_field_data = []
                        submodel = field.related_model

                        for subdata in data:  # Recursively resolve sub dicts
                            if type(subdata) == dict:  # If subdata is a dict, the item was subserialized.
                                sub_field_data.append(
                                    self.get_field_data(subdata, submodel, self.excluded_subfields)
                                )
                            else:  # If subdata is not a dict add it directly
                                sub_field_data.append(subdata)
                        field_data[name] = (field, sub_field_data)  # Add back as a list
                    else:
                        field_data[name] = (field, data)

        return field_data

    def get_viewable_concepts(self, field_data: Dict) -> Dict[int, MDR._concept]:
        """
        Get all concepts linked from this version that are viewable by the user.
        """
        self.ids: List[int] = []
        self.uuids: List[str] = []
        for field_name, field in field_data.values():

            if self.is_concept_fk(field_name):  # If foreign key to concept
                self.ids_or_uuids_appender(field)

            if self.is_concept_multiple(field_name) and type(field) == list:  # If reverse fk or many to many of concept
                for inner_field in field:
                    self.ids_or_uuids_appender(inner_field)

            if type(field) == list:
                for sub_field_data in field:
                    if type(sub_field_data) == dict:
                        for sub_field_name, sub_field in sub_field_data.values():
                            if self.is_concept_fk(sub_field_name):
                                self.ids_or_uuids_appender(sub_field)
                            elif self.is_concept_multiple(sub_field_name) and type(sub_field) == list:
                                for inner_sub_field in sub_field:
                                    self.ids_or_uuids_appender(inner_sub_field)

        return {
            **MDR._concept.objects.filter(id__in=self.ids).visible(self.request.user).in_bulk(),
            **MDR._concept.objects.filter(uuid__in=self.uuids).visible(self.request.user).in_bulk(field_name='uuid'),
        }

    def ids_or_uuids_appender(self, field):
        """
        The purpose of this function is to append an identifier field value (UUID or id) to a list depending on the
        field type.
        This function has been implemented since the UUID (of type str) is the default identifier for relation fields
        in the latest version of the Aristotle API.
        :param field: Union[int, str]: string representation of a UUID field, or integer representation of an id.
        :return: Tuple of lists.
        """
        if isinstance(field, int):
            self.ids.append(field)
        if isinstance(field, str):
            self.uuids.append(field)
        else:  # If this field doesn't have an identifier (because there is nothing currently assigned).
            pass

    def get_lookup_dict(self, field_data) -> LookupDict:
        """
        Get a dictionary with custom fields since values were already filtered.
        :param field_data:
        :return: Dictionary containing a _concept and corresponding CustomFields.
        """

        return {
            MDR._concept._meta.label_lower: self.get_viewable_concepts(field_data),
            CustomField._meta.label_lower: CustomField.objects.in_bulk()
        }

    def get_version_fields(self, field_data, items: LookupDict) -> List[VersionField]:
        """
        Get a list of VersionField objects to render.
        :param field_data: Dictionary mapping a field and the current value.
        :param items: Dictionary.
        :return: List containing VersionField objects.
        """
        fields: List[VersionField] = []
        for field, data in field_data.values():
            lookup_dict: Dict = {}  # Lookup dict for specific model this field links to (if required)
            if field.is_relation:
                related_model = field.related_model
                if issubclass(related_model, MDR._concept):
                    related_model = MDR._concept

                lookup_dict = items.get(related_model._meta.label_lower, {})

            if self.is_link_field(field):  # Add version link field for this data.

                if isinstance(data, str):
                    data = uuid.UUID(data)
                fields.append(
                    VersionLinkField(self.get_verbose_name(field), data, lookup_dict.get(data, None))
                )
            elif type(data) == list:  # If field groups other items get their fields
                sub_fields: List[List[VersionField]] = []
                sub_links: List[VersionLinkField] = []
                for subdata in data:
                    if type(subdata) == dict:  # If dict item was sub-serialized, make a recursive call.
                        sub_fields.append(
                            self.get_version_fields(subdata, items)
                        )
                    elif type(subdata) == int:  # If list has an int, assume it is an id and add link field.
                        sub_links.append(
                            VersionLinkField(self.get_verbose_name(field), subdata, lookup_dict.get(subdata, None))
                        )

                # Group field take priority if there were both (this shouldn't happen though)
                if len(sub_fields) == 0 and len(sub_links) > 0:
                    fields.append(
                        VersionMultiLinkField(self.get_verbose_name(field), sub_links)
                    )
                else:
                    fields.append(
                        VersionGroupField(self.get_verbose_name(field), sub_fields)
                    )
            else:
                # If not foreign key or group
                is_html: bool
                if field.model == CustomValue and 'field' in field_data:
                    is_html = field_data['field'][1] in self.html_custom_field_ids
                else:
                    is_html = self.is_field_obj_html(field)

                fields.append(
                    VersionField(self.get_verbose_name(field), data, is_html)
                )
        return fields

    def get_version_context_data(self) -> Dict:
        """
        Get context data for rendering version fields.
        :return: Dictionary with context data.
        """
        context: dict = {}

        field_data = self.get_field_data(self.version_dict, self.model, self.excluded_fields)  # Get field data
        items = self.get_lookup_dict(field_data)  # Build item data
        context['item_fields'] = self.get_version_fields(field_data, items)

        if self.version_dict['workgroup']:  # Set workgroup object
            try:
                workgroup = MDR.Workgroup.objects.get(pk=self.version_dict['workgroup'])
            except MDR.Workgroup.DoesNotExist:
                workgroup = None

            context['workgroup'] = workgroup

        # Add some extra data the template expects from a regular item object
        context['meta'] = {
            'app_label': self.version.content_type.app_label,
            'model_name': self.version.content_type.model
        }
        context.update({
            'id': self.version.object_id,
            'pk': self.version.object_id,
            'uuid': self.version_dict.get('uuid', ''),
            'name': self.version_dict.get('name', ''),
            'get_verbose_name': self.version.content_type.name.title(),
            'created': self.version_dict['created'],
        })

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'view': self,
            'hide_item_actions': True,
            'hide_item_supersedes': True,
            'hide_item_help': True,
            'hide_item_related': True,
            'item_is_version': True,
            'version_is_most_recent': self.is_most_recent,
            'item': self.get_version_context_data(),
            'current_item': self.item,
            'version': self.version,
            'revision': self.version.revision,
        })
        return context


class ConceptVersionCompareBase(VersionsMixin, TemplateView):
    template_name = 'aristotle_mdr/compare/compare.html'
    hidden_diff_fields = ['modified', 'created', 'uuid', 'serialized_model', 'parent_dss']

    differ = diff_match_patch.diff_match_patch()

    raw = False
    comparing_different_formats = False

    def get_version_1_concept(self):
        raise NotImplementedError

    def get_version_2_concept(self):
        raise NotImplementedError

    def get_compare_versions(self):
        raise NotImplementedError

    def get_model(self, concept) -> Model:
        return concept.item._meta.model

    def both_fields_empty(self, earlier_value, later_value) -> bool:
        """Returns true if both fields do not contain any values"""
        if not earlier_value and not later_value:
            return True
        return False

    def replace_item_id(self, model, field_name, value) -> Optional[Dict]:
        """Returns a modified dict containing item names (and URLs if possible) instead of ids"""
        field = self.get_field_or_none(field_name, model)
        if field is not None:
            if (self.is_concept_fk(field) or self.is_reference_doc_fk(field)) and value:
                if not value.isdigit():
                    return value
                item_model = self.get_model_from_foreign_key_field(model, field_name)
                item = item_model.objects.get(pk=value)
                item_dict = {
                    'name': self.get_item_name(item),
                    'url': self.get_item_url(item)
                }
                return item_dict
        return value

    def get_item_name(self, item) -> str:
        if hasattr(item, 'title'):
            return item.title
        elif hasattr(item, 'name'):
            return item.name
        return ''

    def get_item_url(self, item) -> Optional[str]:
        try:
            return item.get_absolute_url()
        except AttributeError:
            return None

    def diff_field(self, earlier, later) -> List[Tuple]:
        diff = self.differ.diff_main(earlier, later)
        self.differ.diff_cleanupSemantic(diff)

        return diff

    def generate_diff(self, earlier_dict, later_dict):
        """
        Returns a dictionary containing a list of tuples with the differences per field.
        The first element of the tuple specifies if it is an insertion (1), a deletion (-1), or an equality (0).
        Example:
        {field: [(0, hello), (1, world)]}
        """
        field_to_diff = {}

        # Only get the shared field names
        field_names = list(set(earlier_dict.keys()).intersection(set(later_dict.keys())))
        for field in earlier_dict:
            # Iterate through all fields in the dictionary
            show_field = field not in self.hidden_diff_fields and field in field_names
            if show_field:
                # Don't show fields like modified, which are set by the database
                earlier_value = earlier_dict[field]
                later_value = later_dict[field]

                if not self.both_fields_empty(earlier_value, later_value):
                    if isinstance(earlier_value, str) or isinstance(earlier_value, int):
                        # No special treatment required for strings and int
                        earlier = str(earlier_value)
                        later = str(later_value)

                        if not self.raw:
                            # Strip tags if it's not raw
                            earlier = strip_tags(earlier)
                            later = strip_tags(later)

                        is_html_field = self.is_model_field_html(field, self.model)

                        field_to_diff[field] = {'user_friendly_name': field.title(),
                                                'subitem': False,
                                                'is_html': is_html_field,
                                                'diffs': self.diff_field(earlier, later)}

                    elif isinstance(earlier_value, dict):
                        # It's a single subitem
                        subitem_model = self.get_model_from_foreign_key_field(self.model, self.clean_field_name(field))
                        field_to_diff[field] = {
                            'user_friendly_name': self.get_user_friendly_field_name(field, self.model),
                            'subitem': True,
                            'diffs': [self.build_diff_of_item(earlier_value, later_value, subitem_model)]
                        }
                    elif isinstance(earlier_value, list):
                        # It's a list of subitems
                        subitem_model = self.get_model_from_foreign_key_field(self.model, field)

                        field_to_diff[field] = {
                            'user_friendly_name': self.get_user_friendly_field_name(field, self.model),
                            'subitem': True,
                            'diffs': self.build_diff_of_subitems(earlier_value, later_value, subitem_model)}

        return field_to_diff

    def generate_diff_for_added_or_removed_fields(self, ids, values, subitem_model, added=True):
        """ Generates the diff for fields that have been added/removed from a concept comparision"""
        differences = []

        for id in ids:
            item = values[id]
            difference_dict = {}

            for field, value in item.items():
                if field == 'id':
                    pass
                else:
                    if not self.raw:
                        value = strip_tags(str(value))
                    # Because DiffMatchPatch returns a list of tuples of diffs
                    # for consistent display we also return a list of tuples of diffs

                    is_html = False
                    if subitem_model is CustomValue:
                        custom_field_id = item['field']
                        if custom_field_id in self.get_html_custom_field_ids() and field == 'content':
                            is_html = True
                    else:
                        is_html = self.is_model_field_html(field, subitem_model)

                    if added:
                        difference_dict[field] = {'is_html': is_html,
                                                  'diff': [(1, self.replace_item_id(subitem_model, field, value))]}
                    else:
                        difference_dict[field] = {'is_html': is_html,
                                                  'diff': [(-1, self.replace_item_id(subitem_model, field, value))]}
            differences.append(difference_dict)
        return differences

    def get_subitem_key(self, subitem_model) -> str:
        return 'id'

    def is_custom_field_html(self, field, later_item) -> bool:
        custom_field_id = later_item['field']
        if custom_field_id in self.get_html_custom_field_ids() and field == 'content':
            return True
        return False

    def build_diff_of_item(self, earlier_item, later_item, subitem_model) -> Dict[str, Dict]:
        """Function that performs the actual comparision of a subitem"""
        difference_dict = {}

        for field, earlier_value in earlier_item.items():
            if field == 'id':
                # Don't compare ID
                pass
            else:
                later_value = later_item[field]

                earlier_value = str(earlier_value)
                later_value = str(later_value)

                if not self.raw:
                    earlier_value = strip_tags(earlier_value)
                    later_value = strip_tags(later_value)

                # Custom logic to determine if CustomValue field is HTML
                if subitem_model is CustomValue:
                    is_html = self.is_custom_field_html(field, later_item)
                else:
                    is_html = self.is_model_field_html(field, subitem_model)

                difference = [(difference_code, self.replace_item_id(subitem_model, field, difference))
                              for difference_code, difference in self.diff_field(earlier_value, later_value)]

                difference_dict[field] = {'is_html': is_html, 'diff': difference}
        return difference_dict

    def build_diff_of_subitems(self, earlier_values, later_values, subitem_model) -> List[Dict]:
        """
        Given a list of dictionaries containing representations of objects, iterates through and returns a list of
        difference dictionaries per field
        Example:
            [{'field': [(0, hello), (1, world)], 'other_field': [(0, goodbye), (-1, world)]]
        """
        differences: list = []

        if not self.both_fields_empty(earlier_values, later_values):
            key = self.get_subitem_key(subitem_model)

            earlier_items = {item[key]: item for item in earlier_values}
            later_items = {item[key]: item for item in later_values}

            # Items that are in the later items but not the earlier items have been 'added'
            added_ids = set(later_items.keys()) - set(earlier_items.keys())
            added_items = self.generate_diff_for_added_or_removed_fields(added_ids, later_items,
                                                                         subitem_model, added=True)
            if added_items:
                differences.extend(added_items)

            # Items that are in the earlier items but not the later items have been 'removed'
            removed_ids = set(earlier_items.keys()) - set(later_items.keys())
            removed_items = self.generate_diff_for_added_or_removed_fields(removed_ids, earlier_items,
                                                                           subitem_model, added=False)
            if removed_items:
                differences.extend(removed_items)

            # Items with IDs that are present in both earlier and later data have been changed,
            # so we want to perform a field-by-field dict comparision.
            changed_ids = set(earlier_items).intersection(set(later_items))

            for id in changed_ids:
                earlier_item = earlier_items[id]
                later_item = later_items[id]

                difference_dict = self.build_diff_of_item(earlier_item, later_item, subitem_model)
                if difference_dict:
                    differences.append(difference_dict)

        return differences

    def get_version_permission(self, version_1, version_2) -> Tuple[VersionPermissions, VersionPermissions]:
        version_permission_1 = VersionPermissions.objects.get_object_or_none(pk=version_1)
        version_permission_2 = VersionPermissions.objects.get_object_or_none(pk=version_2)

        return version_permission_1, version_permission_2

    def apply_permission_checking(self, version_permission_1, version_permission_2) -> None:
        if not self.user_can_view_version(self.request.user, self.get_version_1_concept(), version_permission_1) and \
                self.user_can_view_version(self.request.user, self.get_version_2_concept(), version_permission_2):
            raise PermissionDenied

    def get_versions(self):
        version_1, version_2 = self.get_compare_versions()

        if not version_1 or not version_2:
            return None

        first_version = reversion.models.Version.objects.get(pk=version_1)
        second_version = reversion.models.Version.objects.get(pk=version_2)

        return first_version, second_version

    def load_version_json(self, first_version, second_version):
        """
        Diffing is order sensitive, so date comparision is performed to ensure that the versions are compared with
        correct chronology.
        """
        first_version_created = first_version.revision.date_created
        second_version_created = second_version.revision.date_created

        reordered = False

        if first_version_created > second_version_created:
            # If the first version is after the second version
            later_version = first_version
            earlier_version = second_version
            reordered = True
        else:
            # The first version is before the second version
            later_version = second_version
            earlier_version = first_version

        versions = {'earlier': earlier_version, 'later': later_version}

        for key, version in versions.items():
            try:
                version = json.loads(version.serialized_data)
            except json.JSONDecodeError:
                return None

            if type(version) == list:
                self.comparing_different_formats = True
                # It's the old version, pull out the actual fields
                version = version[0]['fields']

            versions[key] = version

        return {
            'earlier': versions['earlier'],
            'later': versions['later'],
            'reordered': reordered
        }

    def sanitize_version_json(self, json):
        reordered = json['reordered']
        earlier_json = json['earlier']
        later_json = json['later']

        if not reordered:
            earlier_concept = self.get_version_1_concept()
            later_concept = self.get_version_2_concept()
        else:
            earlier_concept = self.get_version_2_concept()
            later_concept = self.get_version_1_concept()

        # Remove disallowed custom fields
        earlier_json = self.remove_disallowed_custom_fields(
            self.request.user, earlier_json, earlier_concept
        )
        later_json = self.remove_disallowed_custom_fields(
            self.request.user, later_json, later_concept
        )

        return earlier_json, later_json

    def get_version_context_data(self) -> Dict[str, Any]:
        # Get the versions
        versions = self.get_versions()
        if versions is None:
            return {'not_all_versions_selected': True}

        # Get version permission and apply permission checking
        version_permission_1, version_permission_2 = self.get_version_permission(versions[0], versions[1])
        self.apply_permission_checking(version_permission_1, version_permission_2)

        # Load the version json
        json = self.load_version_json(versions[0], versions[1])
        if json is None:
            return {'cannot_compare': True}

        # Sanitize the version json
        earlier_json, later_json = self.sanitize_version_json(json)

        # Perform the diff
        self.raw = self.request.GET.get('raw')
        differences = self.generate_diff(earlier_json, later_json)

        return {
            'diffs': differences,
            'raw': self.raw,
            'version_1_id': versions[0].id,
            'version_2_id': versions[1].id
        }

    def get_context_data(self, **kwargs) -> Dict:
        context = super().get_context_data(**kwargs)
        self.model = self.get_model(self.get_version_1_concept())

        # Get the version context
        context.update(self.get_version_context_data())

        # Basic required template context
        context.update({
            'activetab': 'history',
            'hide_item_actions': True,
            'comparing_different_formats': self.comparing_different_formats
        })
        return context


class ConceptVersionCompareView(SimpleItemGet, ConceptVersionCompareBase):
    """
    View that performs the historical comparision between two different versions of the same concept
    """
    template_name = 'aristotle_mdr/compare/compare.html'
    context: dict = {}

    def get_version_1_concept(self):
        return self.get_item(self.request.user).item

    def get_version_2_concept(self):
        return self.get_item(self.request.user).item

    def get_compare_versions(self):
        version_1 = self.request.GET.get('v1')
        version_2 = self.request.GET.get('v2')

        return version_1, version_2


class ConceptVersionListView(SimpleItemGet, VersionsMixin, ListView):
    """
    View that lists all the specific versions of a particular concept
    """
    template_name = 'aristotle_mdr/compare/versions.html'
    item_action_url = 'aristotle:item_version'

    def get_object(self):
        return self.get_item(self.request.user).item  # Versions are now saved on the model rather than the concept

    @staticmethod
    def get_format_of_version(version):
        return REVERSION_FORMATS[version.format]

    def get_queryset(self) -> List[Dict]:
        """Return a list of all the versions the user has permission to access as well as associated metadata
         involved in template rendering."""
        metadata_item = self.get_object()
        versions = self.get_concept_versions_for_user(metadata_item, self.request.user)

        version_list = []
        version_to_permission = VersionPermissions.objects.in_bulk(versions)
        for version in versions:
            if version.id in version_to_permission:
                version_permission = version_to_permission[version.id]
                if version_permission is None:
                    # Default to displaying workgroup level permissions
                    version_permission_code = VISIBILITY_PERMISSION_CHOICES.workgroup
                else:
                    version_permission_code = version_permission.visibility
            else:
                version_permission_code = VISIBILITY_PERMISSION_CHOICES.workgroup

            version_list.append({
                'format': self.get_format_of_version(version),
                'permission': int(version_permission_code),
                'version': version,
                'revision': version.revision,
                'url': reverse(self.item_action_url, args=[version.id])
            })

        return version_list

    def get_context_data(self, **kwargs):
        # Determine the editing permissions of the user
        metadata_item = self.get_object()
        can_edit = user_can_edit(self.request.user, metadata_item)

        context = {'activetab': 'history',
                   'user_can_edit': can_edit,
                   'object': self.get_object(),
                   'item': self.get_object(),
                   'versions': self.get_queryset(),
                   'choices': VISIBILITY_PERMISSION_CHOICES,
                   "hide_item_actions": True}

        return context


class CompareHTMLFieldsView(SimpleItemGet, VersionsMixin, TemplateView):
    """ A view to render two HTML fields side by side so that they can be compared visually"""
    template_name = 'aristotle_mdr/compare/rendered_field_comparision.html'

    def get_version_json(self, version1, version2) -> Tuple:
        return (get_object_or_404(reversion.models.Version, pk=version1),
                get_object_or_404(reversion.models.Version, pk=version2))

    def get_object(self):
        return self.get_item(self.request.user).item
        # Versions are now saved on the model rather than the concept

    def get_html_fields(self, version_1, version_2, field_query) -> List[str]:
        """Cleans and returns the content for the two versions of a HTML field """
        html_values = []

        fields = tuple(field_query.split('.'))

        versions = [json.loads(version_1.serialized_data),
                    json.loads(version_2.serialized_data)]

        for version_data in versions:
            try:
                version_data = version_data[0]['fields']
            except KeyError:
                pass

            for field in fields:
                if version_data is None:
                    pass
                # Dynamically traverse data structure
                if isinstance(version_data, dict):
                    if field in version_data:
                        version_data = version_data[field]
                    else:
                        version_data = None
                elif isinstance(version_data, list):
                    try:
                        version_data = version_data[int(field)]
                    except IndexError:
                        version_data = None

            if version_data:
                html_values.append(version_data)

        return html_values

    def apply_permission_checking(self, version_permission_1, version_permission_2) -> None:
        if not self.user_can_view_version(self.request.user, self.metadata_item, version_permission_1) and \
                self.user_can_view_version(self.request.user, self.metadata_item, version_permission_2):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        context = {}
        self.metadata_item = self.get_item(self.request.user).item

        version_1 = self.request.GET.get('v1', None)
        version_2 = self.request.GET.get('v2', None)
        field_query = self.request.GET.get('field')

        if not version_1 or not version_2:
            context['not_all_versions_selected'] = True
            return context

        first_version, second_version = self.get_version_json(version_1, version_2)
        version_permission_1 = VersionPermissions.objects.get_object_or_none(pk=version_1)
        version_permission_2 = VersionPermissions.objects.get_object_or_none(pk=version_2)

        self.apply_permission_checking(version_permission_1, version_permission_2)

        context = {'activetab': 'history',
                   'hide_item_actions': True,
                   'item': self.get_object(),
                   'html_fields': self.get_html_fields(version_1=first_version,
                                                       version_2=second_version,
                                                       field_query=field_query)}

        return context
