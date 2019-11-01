import reversion
import json as JSON
from rest_framework import serializers
from drf_writable_nested import WritableNestedModelSerializer

from django.core.serializers.base import Serializer as BaseDjangoSerializer
from django.core.serializers.base import DeserializedObject, build_instance
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr.models import (
    aristotleComponent,
    _concept
)
from aristotle_mdr import utils
from aristotle_mdr.contrib.serializers.utils import (
    get_comet_field_serializer_mapping,
    get_dse_field_serializer_mapping,
    get_aristotle_ontology_serializer_mapping,
    construct_change_message_for_validated_data,
    UUIDRelatedField,
)
from aristotle_mdr.contrib.serializers.concept_general_field_subserializers import (
    IdentifierSerializer,
    SlotsSerializer,
    CustomValuesSerializer,
    OrganisationRecordsSerializer,
)

from aristotle_mdr.contrib.serializers.concept_spcific_field_subserializers import (
    PermissibleValueSerializer,
    SupplementaryValueSerializer,
    ValueMeaningSerializer,
    DedInputsThroughSerializer,
    DedDerivesThroughSerializer,
    RelationRoleSerializer,
)
from aristotle_mdr.required_settings import ARISTOTLE_SETTINGS
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ConceptBaseSerializer(WritableNestedModelSerializer):
    """
    This Class is the serializer representation of the _concept model.
    It includes the universal fields for every _concept instance.
    """
    slots = SlotsSerializer(many=True, required=False)
    customvalue_set = CustomValuesSerializer(many=True, required=False)
    identifiers = IdentifierSerializer(many=True, required=False)
    org_records = OrganisationRecordsSerializer(many=True, required=False)
    stewardship_organisation = serializers.PrimaryKeyRelatedField(
        pk_field=serializers.UUIDField(format='hex'),
        read_only=True,
    )
    submitter = serializers.HiddenField(default=None)

    def validate(self, attrs):

        for field_name, data in self.get_initial().items():  # We are using self.get_initial() because it provides ids.
            if type(data) is list:
                if self.instance is None:
                    for elem in data:
                        if 'id' in elem:
                            msg = _("Parameter `id` is not allowed in POST requests for metadata creation.")
                            raise serializers.ValidationError(msg, code='Aristotle API Request Error')
                        if 'pk' in elem:
                            msg = _("Parameter `pk` is not allowed in POST requests for metadata creation.")
                            raise serializers.ValidationError(msg, code='Aristotle API Request Error')
                else:
                    if not hasattr(self.instance, field_name):
                        msg = _('Object {} of type `{}` does not have any field named "{}"'.format(
                            self.instance, type(self.instance), field_name)
                        )
                        raise serializers.ValidationError(msg, code='Aristotle API Request Error')
                    allowed_ids_for_object_field = set(getattr(self.instance, field_name).values_list('id', flat=True))
                    for elem in data:
                        subcomponent_id = elem.get('id')
                        if subcomponent_id and subcomponent_id not in allowed_ids_for_object_field:
                            msg = _('Id {} does not match with any existing id for {} in {}.'.format(
                                subcomponent_id, field_name, self.instance)
                            )
                            raise serializers.ValidationError(msg, code='Aristotle API Request Error')
        return attrs

    @reversion.create_revision()
    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
            if user.is_authenticated:
                reversion.revisions.set_user(user)
                reversion.revisions.set_comment("Added via {} API.".format(ARISTOTLE_SETTINGS['SITE_NAME']))
                if request.method == 'POST':  # Assign a submitter user only if the item has been created.
                    validated_data["submitter"] = user
            else:
                msg = _('In order to create or update metadata, a user needs to be authenticated.')
                raise serializers.ValidationError(msg, code='Aristotle API Request Error')
        return super().create(validated_data)

    @reversion.create_revision()
    def update(self, instance, validated_data):
        request = self.context.get("request")
        reversion.set_user(request.user)
        reversion.set_comment(construct_change_message_for_validated_data(validated_data, type(self.instance)))
        return super().update(instance, validated_data)


class ConceptSerializerFactory:
    """
    Generalized serializer factory to dynamically set form fields for simpler concepts.
    To begin serializing an added subitem:
        1. Add a ModelSerializer class for your subitem.
        2. Add the class to the field_subserializer_mapping.
    """
    field_subserializer_mapping = {
        'permissiblevalue_set': PermissibleValueSerializer(many=True, required=False),
        'supplementaryvalue_set': SupplementaryValueSerializer(many=True, required=False),
        'valuemeaning_set': ValueMeaningSerializer(many=True),
        'dedinputsthrough_set': DedInputsThroughSerializer(many=True),
        'dedderivesthrough_set': DedDerivesThroughSerializer(many=True),
        'relationrole_set': RelationRoleSerializer(many=True),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.field_subserializer_mapping.update(
            **get_comet_field_serializer_mapping(),
            **get_dse_field_serializer_mapping(),
            **get_aristotle_ontology_serializer_mapping(),
        )

        self.whitelisted_fields = [
            'statistical_unit',
            'dssgrouping_set',
        ] + list(self.field_subserializer_mapping.keys())

    def generate_serializer_class(self, concept_class):
        """
        This function generates a serializer class dynamically.
        :param concept_class: Model class from which we intend to generate a serializer class.
        :return: Class Serializer
        """
        universal_fields = ('slots', 'customvalue_set', 'org_records', 'identifiers', 'stewardship_organisation',
                            'workgroup', 'submitter')

        concept_fields = self._get_concept_fields(concept_class)
        concept_subserialized_relation_fields = self._get_concept_subserialized_relation_fields(concept_class)

        included_fields = concept_fields + concept_subserialized_relation_fields + universal_fields

        # Generate metaclass dynamically
        meta_attrs = {'model': concept_class,
                      'fields': included_fields}
        meta = type('Meta', tuple(), meta_attrs)

        serializer_attrs = {}
        for field_name in concept_subserialized_relation_fields:
            if field_name in self.field_subserializer_mapping:
                # Field is for something that should have it's component fields serialized
                serializer = self.field_subserializer_mapping[field_name]
                serializer_attrs[field_name] = serializer

        # Generate UUID related fields for our Serializer class:
        for field_name in self._get_concept_foreign_keys(concept_class):
            sub_model = concept_class._meta.get_field(field_name).related_model
            serializer_attrs[field_name] = UUIDRelatedField(
                queryset=sub_model.objects.all(), required=False
            )

        serializer_attrs['Meta'] = meta

        # Generate serializer class dynamically
        return type('Serializer', (ConceptBaseSerializer,), serializer_attrs)

    def get_field_name(self, field) -> str:
        if hasattr(field, 'get_accessor_name'):
            return field.get_accessor_name()
        else:
            return field.name

    def _get_concept_fields(self, model_class) -> Tuple:
        """
        Internal helper function to get fields that are actually **on** the model.
        This function excludes Foreign Key fields (relation fields).
        :param model_class: Model to get the fields from.
        :return: Tuple of fields
        """
        fields = []
        for field in model_class._meta.get_fields():
            if not field.is_relation or field.many_to_one:  # Exclude data field or foreign key field
                if not field.name.startswith('_'):  # Don't serialize internal fields
                    fields.append(field.name)

        return tuple(fields)

    def _get_concept_subserialized_relation_fields(self, model_class) -> Tuple:
        """
        Internal helper function to get related (Foreign key) fields which have a subserializer, and
        fields that have been added to the class whitelist of allowed fields.
        :param model_class: Model to get the subserialized fields from.
        :return: Tuple of fields.
        """
        related_fields = []

        for field in model_class._meta.get_fields():
            if not field.name.startswith('_'):  # Don't serialize internal fields.
                if field.is_relation:
                    # Check if the model class is the parent of the item, we don't want to serialize up the chain
                    field_model = field.related_model
                    if issubclass(field_model, aristotleComponent):
                        # If it's a subclass of aristotleComponent it should have a parent
                        parent_model = field_model.get_parent_model()
                        if not parent_model:
                            # This aristotle component has no parent model
                            related_fields.append(self.get_field_name(field))
                        else:
                            if field_model.get_parent_model() == model_class:
                                # If the parent is the model we're serializing, right now
                                related_fields.append(self.get_field_name(field))
                            else:
                                # It's the child, we don't want to serialize
                                pass
                    else:
                        # Just a normal field
                        related_fields.append(self.get_field_name(field))

        return tuple([field for field in related_fields if field in self.whitelisted_fields])

    def _get_concept_foreign_keys(self, model_class) -> Tuple:
        """
        The purpose of this function is to get the _concept subclassed related fields (`_concept` Foreign Keys) from a
        model.
        :param model_class: Model to get the Foreign Key fields from.
        :return: Tuple of Foreign Key fields.
        """
        related_fields = []

        for field in model_class._meta.get_fields():
            if not field.name.startswith('_'):  # Don't serialize internal fields.
                if field.is_relation and field.many_to_one:
                    if issubclass(field.related_model, _concept):  # If the related model is a subclass of _concept.
                        related_fields.append(self.get_field_name(field))

        return tuple([field for field in related_fields])

    def generate_deserializer(self, json):
        """ Generate the deserializer """
        concept_model = self._get_class_for_deserializer(json)

        Deserializer = self.generate_serializer_class(concept_model)
        return Deserializer

    def _get_class_for_deserializer(self, json):
        data = JSON.loads(json)
        return apps.get_model(data['serialized_model'])


class Serializer(BaseDjangoSerializer):
    """
    This is a django serializer that has a 'composed' DRF Serializer inside.
    """
    data: dict = {}

    def serialize(self, queryset, stream=None, fields=None, use_natural_foreign_keys=False,
                  use_natural_primary_keys=False, progress_output=None, **options):
        item = queryset[0]

        # Generate the serializer class dynamically
        serialiser_class = ConceptSerializerFactory().generate_serializer_class(type(item))

        # Instantiate the serializer
        serializer = serialiser_class(item)

        # Add the app label as a key to the json so that the deserializer can be generated
        data = serializer.data
        data['serialized_model'] = item._meta.label_lower

        self.data = JSON.dumps(data)

    def getvalue(self):
        # Get value must be overridden because django-reversion calls *getvalue* rather than serialize directly
        return self.data


def Deserializer(json, using=DEFAULT_DB_ALIAS, **options):
    # TODO: fix
    """
    Deserialize JSON back into Django ORM instances.
    Django deserializers yield a DeserializedObject generator.
    DeserializedObjects are thin wrappers over POPOs.
    """
    m2m_data = {}

    # Generate the serializer
    ModelDeserializer = ConceptSerializerFactory().generate_deserializer(json)

    # Instantiate the serializer
    data = JSON.loads(json)

    Model = apps.get_model(data['serialized_model'])

    # Deserialize the data
    serializer = ModelDeserializer(data=data)

    serializer.is_valid(raise_exception=True)

    obj = build_instance(Model, data, using)

    yield DeserializedObject(obj, m2m_data)
