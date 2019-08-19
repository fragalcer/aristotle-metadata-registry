from django.db.models.query import QuerySet
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.views.generic.list import ListView
from django.views.generic import TemplateView
from django.db.models import Q, Model, Field
from django.urls import reverse
from django.core.exceptions import FieldDoesNotExist
from django.shortcuts import get_object_or_404

from aristotle_mdr import models as MDR
from aristotle_mdr.perms import user_can_edit
from aristotle_mdr.constants import visibility_permission_choices as VISIBILITY_PERMISSION_CHOICES
from aristotle_mdr.views.utils import SimpleItemGet
from aristotle_mdr.utils.utils import strip_tags
from aristotle_mdr.contrib.custom_fields.models import CustomField, CustomValue
from aristotle_mdr.contrib.publishing.models import VersionPermissions
from aristotle_mdr.contrib.custom_fields.models import CustomField
from aristotle_mdr.utils.versions import VersionField, VersionLinkField, VersionGroupField, VersionMultiLinkField

from ckeditor_uploader.fields import RichTextUploadingField as RichTextField
from typing import Dict, List, Optional, Tuple, Any, Set, NamedTuple
import json
import reversion
import diff_match_patch

import logging
logger = logging.getLogger(__name__)

# Type alias
LookupDict = Dict[str, Dict[int, Any]]


class VersionsMixin:
    """Mixin providing helper functionality to views handling version data"""

    def user_can_view_version(self, user, metadata_item, version_permission: VersionPermissions) -> bool:
        """ Determine whether or not user can view the specific version """

        in_workgroup = metadata_item.workgroup and user in metadata_item.workgroup.member_list
        authenticated_user = not user.is_anonymous

        if user.is_superuser:
            # Superusers can see everything
            return True

        if metadata_item.stewardship_organisation is None \
                and metadata_item.workgroup is None and metadata_item.submitter_id == user.id:
            # If you submitted the item and it has not been passed onto a workgroup or stewardship organisation
            return True

        if version_permission is None:
            # Default to applying workgroup permissions
            if in_workgroup:
                return True
        else:
            visibility = int(version_permission.visibility)

            if visibility == VISIBILITY_PERMISSION_CHOICES.workgroup:
                # Apply workgroup permissions
                if in_workgroup:
                    return True

            elif visibility == VISIBILITY_PERMISSION_CHOICES.auth:
                # Exclude anonymous users
                if authenticated_user:
                    return True
            else:
                # Visibility is public, don't exclude
                return True

        return False

    def get_versions(self, concept, user) -> QuerySet:
        """ Get versions and apply permission checking so that only versions that the user is allowed to see are
        shown """

        versions = reversion.models.Version.objects.get_for_object(concept).select_related("revision__user")

        # Determine the viewing permissions of the users
        if not user.is_superuser:
            # Superusers can see everything, for performance we won't look up version permission objs
            version_to_permission = VersionPermissions.objects.in_bulk(versions)

            for version in versions:
                if version.id in version_to_permission:
                    version_permission = version_to_permission[version.id]
                else:
                    version_permission = None
                if not self.user_can_view_version(user, concept, version_permission):
                    versions = versions.exclude(pk=version.pk)

        versions = versions.order_by('-revision__date_created')

        return versions

    def is_field_html(self, fieldname: str, model: Model) -> bool:
        try:
            fieldobj = model._meta.get_field(fieldname)
        except FieldDoesNotExist:
            return False
        return self.is_field_obj_html(fieldobj)

    def is_field_obj_html(self, field: Field) -> bool:
        return issubclass(type(field), RichTextField)

    def get_html_custom_field_ids(self) -> Set[int]:
        ids_qs = CustomField.objects.filter(type='html').values_list('id', flat=True)
        return set(ids_qs)

    def get_model_from_foreign_key_field(self, parent_model: Model, field) -> Model:
        try:
            return parent_model._meta.get_field(field).related_model
        except FieldDoesNotExist:
            return parent_model._meta.get_field(self.clean_field(field)).related_model

    def clean_field(self, field: str) -> str:
        postfix = '_set'
        if field.endswith(postfix):
            return field[:-len(postfix)]
        return field

    def get_field(self, field_name: str, model) -> Field:
        try:
            field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            field = model._meta.get_field(self.clean_field(field_name))
        return field

    def get_field_or_none(self, field_name: str, model) -> Optional[Field]:
        try:
            field = self.get_field(field_name, model)
        except FieldDoesNotExist:
            field = None
        return field

    def get_user_friendly_field_name(self, field: str, model) -> str:
        # If the field ends with _set we want to remove it, so we can look it up in the _meta.
        fieldobj = self.get_field(field, model)
        try:
            name = self.get_verbose_name(fieldobj)
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
        """ Remove disallowed/deactivated custom fields from data structure """
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
        """Check whether field is a foreign key to a concept"""
        return field.many_to_one and issubclass(field.related_model, MDR._concept)

    def is_link_field(self, field) -> bool:
        """Check whether field is a foreign key to an item we want to display lookup value for"""
        if field.many_to_one:
            related = field.related_model
            return issubclass(related, MDR._concept) or related == CustomField
        return False


class ConceptVersionView(VersionsMixin, TemplateView):
    """Display the version of a concept at a particular point"""

    template_name = 'aristotle_mdr/concepts/managedContentVersion.html'
    version_arg = 'verid'
    # Top level fields to exclude
    excluded_fields = ['id', 'uuid', 'name', 'version', 'submitter', 'created', 'modified', 'serialized_model']
    # Excluded fields on subserialized items
    excluded_subfields = ['id', 'group']

    def dispatch(self, request, *args, **kwargs):
        self.version = self.get_version()
        self.model = self.version.content_type.model_class()
        self.item = self.get_item(self.version)

        # Check it's a concept version
        if not issubclass(self.model, MDR._concept):
            raise Http404

        # Get version permission
        try:
            self.version_permission = VersionPermissions.objects.get(pk=self.version.pk)
        except VersionPermissions.DoesNotExist:
            self.version_permission = None

        # Check if version can be viewed
        if not self.check_item(self.item, self.version_permission):
            raise PermissionDenied

        # Deserialize version data
        self.version_dict = self.get_version_data(self.version.serialized_data, self.item)

        # Fetch html custom field ids
        self.html_custom_field_ids: Set[int] = self.get_html_custom_field_ids()

        return super().dispatch(request, *args, **kwargs)

    def check_item(self, item, version_permission):
        """Permissions checking on version"""
        # Will 403 Forbidden when user can't view the version
        return self.user_can_view_version(self.request.user, item, version_permission)

    def get_item(self, version):
        """Get current item from version"""
        return version.object

    def get_version(self) -> reversion.models.Version:
        """Lookup version object"""
        return get_object_or_404(reversion.models.Version, id=self.kwargs[self.version_arg])

    def get_version_data(self, version_json: str, item: MDR._concept):
        """Deserialize and filter version data"""
        version_dict: Dict = {}
        try:
            version_dict = json.loads(version_json)
        except json.JSONDecodeError:
            # Handle bad serialized data
            raise Http404

        return self.remove_disallowed_custom_fields(self.request.user, version_dict, item)

    def is_concept_multiple(self, field):
        """Check whether field is a link to multiple concepts"""
        return (field.many_to_many or field.one_to_many) and issubclass(field.related_model, MDR._concept)

    def get_field_data(self, version_data: Dict, model, exclude: List[str] = []) -> Dict:
        """Replace data with (field, data) tuples"""
        field_data = {}

        for name, data in version_data.items():
            # If field name isnt excluded or we are not excluding
            if name not in exclude or not exclude:
                field = self.get_field_or_none(name, model)
                if field:
                    # If field is subserialized
                    if type(data) == list and field.is_relation:
                        sub_field_data = []
                        submodel = field.related_model

                        # Recursively resolve sub dicts
                        for subdata in data:
                            if type(subdata) == dict:
                                # If subdata is dict item that was subserialized
                                sub_field_data.append(
                                    self.get_field_data(subdata, submodel, self.excluded_subfields)
                                )
                            else:
                                # If subdata is not a dict add it directly
                                sub_field_data.append(subdata)
                        # Add back as a list
                        field_data[name] = (field, sub_field_data)
                    else:
                        field_data[name] = (field, data)

        return field_data

    def get_viewable_concepts(self, field_data: Dict) -> Dict[int, MDR._concept]:
        """Get all concepts linked from this version that are viewable by the user"""
        ids = []
        for field, data in field_data.values():
            # If foreign key to concept
            if self.is_concept_fk(field):
                ids.append(data)

            # If reverse fk or many to many of concept
            if self.is_concept_multiple(field) and type(data) == list:
                ids.extend(data)

            if type(data) == list:
                for subdata in data:
                    if type(subdata) == dict:
                        for subfield, subvalue in subdata.values():
                            if self.is_concept_fk(subfield):
                                ids.append(subvalue)
                            elif self.is_concept_multiple(subfield) and type(subvalue) == list:
                                ids.extend(subvalue)

        return MDR._concept.objects.filter(id__in=ids).visible(self.request.user).in_bulk()

    def get_lookup_dict(self, field_data) -> LookupDict:
        lookup = {}
        lookup[MDR._concept._meta.label_lower] = self.get_viewable_concepts(field_data)
        # Get all custom fields since values already filtered
        lookup[CustomField._meta.label_lower] = CustomField.objects.in_bulk()
        return lookup

    def get_version_fields(self, field_data, items: LookupDict) -> List[VersionField]:
        """Get a list of VersionField objects to render"""
        fields: List[VersionField] = []
        for field, data in field_data.values():
            # Get lookup dict for specific model this field links to (if required)
            lookup: Dict = {}
            if field.is_relation:
                related = field.related_model
                if issubclass(related, MDR._concept):
                    related = MDR._concept
                lookup = items.get(related._meta.label_lower, {})

            if self.is_link_field(field):
                # Add version link field for this data
                fields.append(
                    VersionLinkField(self.get_verbose_name(field), data, lookup.get(data, None))
                )
            elif type(data) == list:
                # If field groups other items get their fields
                sub_fields: List[List[VersionField]] = []
                sub_links: List[VersionLinkField] = []
                for subdata in data:
                    if type(subdata) == dict:
                        # If dict item was sub-serialized. Make recursive call
                        sub_fields.append(
                            self.get_version_fields(subdata, items)
                        )
                    elif type(subdata) == int:
                        # If list has an int, assume id and add link field
                        sub_links.append(
                            VersionLinkField(self.get_verbose_name(field), subdata, lookup.get(subdata, None))
                        )

                # Group field take priority if there were both (this shouldnt happen though)
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
        """Get context data for rendering version fields"""
        context: dict = {}

        # Get field data
        field_data = self.get_field_data(self.version_dict, self.model, self.excluded_fields)

        # Build item data
        items = self.get_lookup_dict(field_data)
        context['item_fields'] = self.get_version_fields(field_data, items)

        # Set workgroup object
        if self.version_dict['workgroup']:
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

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({
            'view': self,
            'hide_item_actions': True,
            'hide_item_supersedes': True,
            'hide_item_help': True,
            'hide_item_related': True,
            'item_is_version': True,
            'item': self.get_version_context_data(),
            'current_item': self.item,
            'version': self.version,
            'revision': self.version.revision,
        })
        return context


class ConceptVersionCompareBase(VersionsMixin, TemplateView):
    template_name = 'aristotle_mdr/compare/compare.html'
    context: dict = {}
    hidden_diff_fields = ['modified', 'created', 'uuid', 'serialized_model', 'parent_dss']

    differ = diff_match_patch.diff_match_patch()
    raw = False

    def both_fields_empty(self, earlier_value, later_value):
        if not earlier_value and not later_value:
            return True
        return False

    def perform_diff_on_field(self, earlier, later):
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

                        is_html_field = self.is_field_html(field, self.model)

                        field_to_diff[field] = {'user_friendly_name': field.title(),
                                                'subitem': False,
                                                'is_html': is_html_field,
                                                'diffs': self.perform_diff_on_field(earlier, later)}

                    elif isinstance(earlier_value, dict):
                        # It's a single subitem
                        subitem_model = self.get_model_from_foreign_key_field(self.model, self.clean_field(field))
                        field_to_diff[field] = {
                            'user_friendly_name': self.get_user_friendly_field_name(field, self.model),
                            'subitem': True,
                            'diffs': self.build_diff_of_subitem_dict(earlier_value, later_value,
                                                                     subitem_model)
                        }
                    elif isinstance(earlier_value, list):
                        # It's a list of subitems
                        subitem_model = self.get_model_from_foreign_key_field(self.model, field)

                        field_to_diff[field] = {
                            'user_friendly_name': self.get_user_friendly_field_name(field, self.model),
                            'subitem': True,
                            'diffs': self.build_diff_of_subitems(earlier_value, later_value, subitem_model)}

        return field_to_diff

    def generate_diff_for_added_removed_fields(self, ids, values, subitem_model, added=True):
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
                        is_html = self.is_field_html(field, subitem_model)

                    if added:
                        difference_dict[field] = {'is_html': is_html,
                                                  'diff': [(1, value)]}
                    else:
                        difference_dict[field] = {'is_html': is_html,
                                                  'diff': [(-1, value)]}
            differences.append(difference_dict)
        return differences

    def build_diff_of_subitem_dict(self, earlier_item, later_item, subitem_model) -> List[Dict]:
        difference_dict = {}

        for field, earlier_value in earlier_item.items():
            if field == 'id':
                pass
            else:
                later_value = later_item[field]
                if not self.raw:
                    earlier_value = strip_tags(str(earlier_value))
                    later_value = strip_tags(str(later_value))

                if earlier_value is None:
                    # Can't perform a diff on a null value
                    earlier_value = 'None'

                if later_value is None:
                    later_value = 'None'

                difference_dict[field] = {'is_html': self.is_field_html(field, subitem_model),
                                          'diff': self.perform_diff_on_field(earlier_value, later_value)}
        return [difference_dict]

    def get_subitem_key(self, subitem_model):
        return 'id'

    def replace_id_with_names(self, model, items):
        for subitem in items.values():
            # Iterate over subitems
            for field_name, value in subitem.items():
                field = self.get_field_or_none(field_name, model)
                if field is None:
                    pass
                else:
                    if self.is_concept_fk(field):
                        # Perform the lookup, modify in place
                        item_model = self.get_model_from_foreign_key_field(model, field_name)
                        item_name = item_model.objects.get(pk=value).name
                        subitem[field_name] = item_name
        return items

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
            earlier_items = self.replace_id_with_names(subitem_model, earlier_items)

            later_items = {item[key]: item for item in later_values}
            later_items = self.replace_id_with_names(subitem_model, later_items)

            # Items that are in the later items but not the earlier items have been 'added'
            added_ids = set(later_items.keys()) - set(earlier_items.keys())
            added_items = self.generate_diff_for_added_removed_fields(added_ids, later_items,
                                                                      subitem_model, added=True)
            if added_items:
                differences.extend(added_items)

            # Items that are in the earlier items but not the later items have been 'removed'
            removed_ids = set(earlier_items.keys()) - set(later_items.keys())
            removed_items = self.generate_diff_for_added_removed_fields(removed_ids, earlier_items,
                                                                        subitem_model, added=False)
            if removed_items:
                differences.extend(removed_items)

            # Items with IDs that are present in both earlier and later data have been changed,
            # so we want to perform a field-by-field dict comparision.
            changed_ids = set(earlier_items).intersection(set(later_items))
            for id in changed_ids:
                earlier_item = earlier_items[id]
                later_item = later_items[id]

                difference_dict = {}

                for field, earlier_value in earlier_item.items():
                    if field == 'id':
                        pass
                    else:
                        later_value = later_item[field]

                        earlier_value = str(earlier_value)
                        later_value = str(later_value)

                        if not self.raw:
                            earlier_value = strip_tags(earlier_value)
                            later_value = strip_tags(later_value)

                        # Custom logic to determine if CustomValue field is HTML
                        is_html = False
                        if subitem_model is CustomValue:
                            custom_field_id = later_item['field']
                            if custom_field_id in self.get_html_custom_field_ids() and field == 'content':
                                is_html = True
                        else:
                            is_html = self.is_field_html(field, subitem_model)

                        difference_dict[field] = {'is_html': is_html,
                                                  'diff': self.perform_diff_on_field(earlier_value, later_value)}
                if difference_dict:
                    differences.append(difference_dict)

        return differences

    def get_version_jsons(self, first_version, second_version):
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

        return (
            json.loads(earlier_version.serialized_data),
            json.loads(later_version.serialized_data),
            reordered
        )

    def get_model(self, concept) -> Model:
        return concept.item._meta.model

    def get_version_1_concept(self):
        raise NotImplementedError

    def get_version_2_concept(self):
        raise NotImplementedError

    def apply_permission_checking(self, version_permission_1, version_permission_2):
        if not self.user_can_view_version(self.request.user, self.get_version_1_concept(), version_permission_1) and \
                self.user_can_view_version(self.request.user, self.get_version_2_concept(), version_permission_2):
            raise PermissionDenied

    def get_compare_versions(self):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        self.context = super().get_context_data(**kwargs)

        self.context['activetab'] = 'history'
        self.context['hide_item_actions'] = True

        version_1, version_2 = self.get_compare_versions()

        if not version_1 or not version_2:
            self.context['not_all_versions_selected'] = True
            return self.context

        self.model = self.get_model(self.get_version_1_concept())

        first_version = reversion.models.Version.objects.get(pk=version_1)
        second_version = reversion.models.Version.objects.get(pk=version_2)
        version_permission_1 = VersionPermissions.objects.get_object_or_none(pk=version_1)
        version_permission_2 = VersionPermissions.objects.get_object_or_none(pk=version_2)

        self.apply_permission_checking(version_permission_1, version_permission_2)

        # Need to pass this context to rebuild query parameters in template
        self.context['version_1_id'] = version_1
        self.context['version_2_id'] = version_2

        try:
            earlier_json, later_json, reordered = self.get_version_jsons(first_version, second_version)
        except json.JSONDecodeError:
            self.context['cannot_compare'] = True
            return self.context

        if not reordered:
            earlier_concept = self.get_version_1_concept()
            later_concept = self.get_version_2_concept()
        else:
            earlier_concept = self.get_version_2_concept()
            later_concept = self.get_version_1_concept()

        earlier_json = self.remove_disallowed_custom_fields(
            self.request.user, earlier_json, earlier_concept
        )
        later_json = self.remove_disallowed_custom_fields(
            self.request.user, later_json, later_concept
        )

        self.raw = self.request.GET.get('raw')
        if self.raw:
            self.context['raw'] = True
            self.context['diffs'] = self.generate_diff(earlier_json, later_json)
        else:
            self.context['diffs'] = self.generate_diff(earlier_json, later_json)

        return self.context


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
        return (version_1, version_2)


class ConceptVersionListView(SimpleItemGet, VersionsMixin, ListView):
    """
    View  that lists all the specific versions of a particular concept
    """
    template_name = 'aristotle_mdr/compare/versions.html'
    item_action_url = 'aristotle:item_version'

    def get_object(self):
        return self.get_item(self.request.user).item  # Versions are now saved on the model rather than the concept

    def get_queryset(self) -> List[Dict]:
        """Return a queryset of all the versions the user has permission to access as well as associated metadata
         involved in template rendering"""
        metadata_item = self.get_object()
        versions = self.get_versions(metadata_item, self.request.user)

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
        return self.get_item(self.request.user).item  # Versions are now saved on the model rather than the concept

    def get_html_fields(self, version_1, version_2, field_query) -> List[str]:
        """Cleans and returns the content for the two versions of a HTML field """
        html_values = []

        fields = tuple(field_query.split('.'))

        versions = [json.loads(version_1.serialized_data),
                    json.loads(version_2.serialized_data)]

        for version in versions:
            version_data = version
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

    def apply_permission_checking(self, version_permission_1, version_permission_2):
        if not self.user_can_view_version(self.request.user, self.metadata_item, version_permission_1) and \
                self.user_can_view_version(self.request.user, self.metadata_item, version_permission_2):
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        self.metadata_item = self.get_item(self.request.user).item

        context = {'activetab': 'history',
                   'hide_item_actions': True,
                   'item': self.get_object()}

        version_1 = self.request.GET.get('v1', None)
        version_2 = self.request.GET.get('v2', None)

        if not version_1 or not version_2:
            context['not_all_versions_selected'] = True
            return context

        first_version, second_version = self.get_version_json(version_1, version_2)

        version_permission_1 = VersionPermissions.objects.get_object_or_none(pk=version_1)
        version_permission_2 = VersionPermissions.objects.get_object_or_none(pk=version_2)

        self.apply_permission_checking(version_permission_1, version_permission_2)

        field_query = self.request.GET.get('field')
        context['html_fields'] = self.get_html_fields(first_version, second_version, field_query)

        return context
