"""A collection of util functions to help """
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from rest_framework import serializers
from django.utils.translation import ugettext as _
from django.utils.text import get_text_list
from aristotle_mdr.models import aristotleComponent


class UUIDRelatedField(serializers.RelatedField):
    """
    UUID Related field for Aristotle Serializers.
    """

    def to_internal_value(self, data):
        try:
            return self.get_queryset().get(uuid=data)
        except ObjectDoesNotExist:
            msg = _("UUID `{}` does not match with any existing UUID for "
                    "this type of metadata object.".format(str(data)))
            raise ValidationError(msg, code='Aristotle Serializer Error')

    def to_representation(self, value):
        return str(value.uuid)


class SubSerializer(serializers.ModelSerializer):
    """
    Base class for subserializers.
    """
    id = serializers.SerializerMethodField()

    def get_id(self, item):
        """Get pk here in case we are not using the auto id field"""
        return item.pk


class AristotleComponentSerializer(serializers.ModelSerializer):
    """
    Base class for Aristotle Components.
    """

    id = serializers.UUIDField(required=False)


def get_comet_field_serializer_mapping():
    mapping = {}
    if 'comet' in settings.INSTALLED_APPS:
        from aristotle_mdr.contrib.serializers.comet_indicator_serializers import (
            IndicatorNumeratorSerializer,
            IndicatorDenominatorSerializer,
            IndicatorDisaggregationSerializer,
            IndicatorInclusionSerializer,
            FrameworkDimensionSerializer,
        )

        mapping = {
            'indicatornumeratordefinition_set': IndicatorNumeratorSerializer(many=True),
            'indicatordenominatordefinition_set': IndicatorDenominatorSerializer(many=True),
            'indicatordisaggregationdefinition_set': IndicatorDisaggregationSerializer(many=True),
            'indicatorinclusion_set': IndicatorInclusionSerializer(many=True),
            'frameworkdimension_set': FrameworkDimensionSerializer(many=True),
        }
    return mapping


def get_dse_field_serializer_mapping():
    mapping = {}
    if 'aristotle_dse' in settings.INSTALLED_APPS:
        # Add extra serializers if DSE is installed
        from aristotle_mdr.contrib.serializers.dse_serializers import (
            DSSGroupingSerializer,
            DSSClusterInclusionSerializer,
            DSSDEInclusionSerializer,
            DistributionDataElementPathSerializer,
        )

        mapping = {
            'dssclusterinclusion_set': DSSClusterInclusionSerializer(many=True),
            'dssdeinclusion_set': DSSDEInclusionSerializer(many=True),
            'groups': DSSGroupingSerializer(many=True),
            'distributiondataelementpath_set': DistributionDataElementPathSerializer(many=True),
        }
    return mapping


def get_aristotle_ontology_serializer_mapping():
    mapping = {}
    if 'aristotle_ontology' in settings.INSTALLED_APPS:
        from aristotle_mdr.contrib.serializers.aristotle_ontology_serializers import (
            ObjectClassSpecialisationNarrowerClassSerializer
        )

        mapping = {
            'objectclassspecialisationnarrowerclass_set': ObjectClassSpecialisationNarrowerClassSerializer(many=True, required=False),
        }
    return mapping


def construct_change_message_for_validated_data(validated_data, model=None):
    """
    This function returns the string representation of the modified fields from an API serialized data.
    Particularly useful in update() functions of Serializers.

    The change message returned by this function ignores the item submitter.

    :param validated_data: Dictionary containing field names as keys and changed values.
    :param model: Model from which the fields' verbose names will be retrieved.
    :return: String. Description of the modified fields of a serializer's validated data.
    """

    change_message = ""
    fields_verbose_names = []
    field_names_list = list(validated_data.keys())

    if 'submitter' in field_names_list:  # We don't need the `user` field in our change message.
        field_names_list.remove('submitter')

    for field_name in field_names_list:
        field = model._meta.get_field(field_name)
        if field.is_relation:
            fields_verbose_names.append(field.related_model._meta.verbose_name.lower())
        else:
            fields_verbose_names.append(field.verbose_name)

    if fields_verbose_names:
        change_message = _('Changed %s.') % get_text_list(fields_verbose_names, _('and'))

    return change_message


def get_concept_fields(model_class):
    fields = []
    for field in model_class._meta.get_fields():
        if not field.is_relation:
            if not field.name.startswith('_'):
                # Don't serialize internal fields
                fields.append(field)
    return fields


def get_many_to_one_fields(model_class):
    fields = []
    for field in model_class._meta.get_fields():
        if field.many_to_one:
            if not field.name.startswith("_"):
                fields.append(field)
    return fields


def get_concept_field_names(model_class):
    """Get fields that are actually **on** the model or are many-to-one.
       Returns a tuple of fields"""
    fields = get_concept_fields(model_class) + get_many_to_one_fields(model_class)
    return tuple([field.name for field in fields])


def get_field_name(field):
    if hasattr(field, 'get_accessor_name'):
        return field.get_accessor_name()
    else:
        return field.name


def get_relation_fields(model_class):
    """
    Helper function to get related fields
    Returns a tuple of fields
    """
    related_fields = []
    for field in model_class._meta.get_fields():
        if not field.name.startswith('_'):
            # Don't serialize internal fields
            if field.is_relation:
                # Check if the model class is the parent of the item, we don't want to serialize up the chain
                field_model = field.related_model
                if issubclass(field_model, aristotleComponent):
                    # If it's a subclass of aristotleComponent it should have a parent
                    parent_model = field_model.get_parent_model()
                    if not parent_model:
                        # This aristotle component has no parent model
                        related_fields.append(field)
                    else:
                        if field_model.get_parent_model() == model_class:
                            # If the parent is the model we're serializing, right now
                            related_fields.append(field)
                        else:
                            # It's the child, we don't want to serialize
                            pass
                else:
                    # Just a normal field
                    related_fields.append(field)

    return related_fields


def get_relation_field_names(model_class, whitelisted_fields=None):
    fields = get_relation_fields(model_class)
    if whitelisted_fields:
        return tuple([get_field_name(field) for field in fields if get_field_name(field) in whitelisted_fields])
    else:
        return tuple([get_field_name(field) for field in fields])
