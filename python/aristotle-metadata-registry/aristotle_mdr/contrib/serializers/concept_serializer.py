"""
Serializer for concept and all attached fields
"""
from rest_framework import serializers

from django.core.serializers.base import Serializer as BaseDjangoSerializer
from django.core.serializers.base import DeserializedObject, build_instance
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS
from django.conf import settings

from aristotle_mdr.contrib.custom_fields.models import CustomValue
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.contrib.identifiers.models import ScopedIdentifier
from aristotle_mdr.models import RecordRelation, ValueDomain, DataElementConcept

import json as JSON

import logging

logger = logging.getLogger(__name__)


class IdentifierSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField(method_name='get_id')

    class Meta:
        model = ScopedIdentifier
        fields = ['namespace', 'identifier', 'version', 'order']

    def get_id(self, identifier):
        return identifier.pk


class CustomValuesSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = CustomValue
        fields = ['field', 'content', 'id']

    def get_id(self, custom_value):
        return custom_value.field.id


class SlotsSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = Slot
        fields = ['name', 'value', 'order', 'permission', 'id']

    def get_id(self, slot):
        return slot.pk


class OrganisationRecordsSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = RecordRelation
        fields = ['organization_record', 'type', 'id']

    def get_id(self, org_record):
        return org_record.pk


class ValueDomainSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = ValueDomain
        fields = ['name']

    def get_name(self, value_domain):
        return value_domain.name


class DataElementConceptSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = DataElementConcept
        fields = ['name']

    def get_name(self, data_element_concept):
        return data_element_concept.name


class BaseSerializer(serializers.ModelSerializer):
    slots = SlotsSerializer(many=True)
    customvalue_set = CustomValuesSerializer(many=True)

    identifiers = IdentifierSerializer(many=True)
    org_records = OrganisationRecordsSerializer(many=True)

    stewardship_organisation = serializers.PrimaryKeyRelatedField(
        pk_field=serializers.UUIDField(format='hex'),
        read_only=True)

# To begin serializing an added subitem:
#   1. Add a ModelSerializer for your subitem
#   2. Add to whitelisted relation_fields
#   3. Add to FIELD_SUBSERIALIZER_MAPPING


class ConceptSerializerFactory():
    """ Generalized serializer factory to dynamically set form fields for simpler concepts """
    FIELD_SUBSERIALIZER_MAPPING = {
        'valueDomain': ValueDomainSerializer(),
        'dataElementConcept': DataElementConceptSerializer()}

    if 'aristotle_dse' in settings.INSTALLED_APPS:
        # Add extra serializers if DSE is installed
        from aristotle_mdr.contrib.serializers.dse_serializers import (
            DSSGroupingSerializer, DSSClusterInclusionSerializer, DSSDEInclusionSerializer
        )

        FIELD_SUBSERIALIZER_MAPPING.update({'dssdeinclusion_set': DSSDEInclusionSerializer(many=True),
                                            'dssclusterinclusion_set': DSSClusterInclusionSerializer(many=True),
                                            'groups': DSSGroupingSerializer(many=True)})

    def _get_concept_fields(self, model_class):
        """Internal helper function to get fields that are actually **on** the model.
           Returns a tuple of fields"""
        fields = []
        for field in model_class._meta.get_fields():
            if not field.is_relation:
                if not field.name.startswith('_'):
                    # Don't serialize internal fields
                    fields.append(field.name)

        return tuple(fields)

    def _get_relation_fields(self, model_class):
        """ Internal helper function to get related fields
            Returns a tuple of fields"""
        whitelisted_fields = ['dssdeinclusion_set',
                              'dssclusterinclusion_set',
                              'parent_dss',
                              'indicatornumeratordefinition_set',
                              'indicatordenominatordefinition_set',
                              'indicatordisaggregationdefinition_set',
                              'statistical_unit',
                              'dssgrouping_set',
                              'groups',  # Related name for DSS Groupings
                              'valueDomain',
                              'dataElementConcept']
        related_fields = []
        for field in model_class._meta.get_fields():
            if not field.name.startswith('_'):
                # Don't serialize internal fields
                if field.is_relation:
                    if hasattr(field, 'get_accessor_name'):
                        related_fields.append(field.get_accessor_name())
                    else:
                        related_fields.append(field.name)

        return tuple([field for field in related_fields if field in whitelisted_fields])

    def _get_class_for_serializer(self, concept):
        return concept.__class__

    def generate_serializer(self, concept):
        """ Generate the serializer class """
        concept_class = self._get_class_for_serializer(concept)
        Serializer = self._generate_serializer_class(concept_class)

        return Serializer

    def _generate_serializer_class(self, concept_class):

        universal_fields = ('slots', 'customvalue_set', 'org_records', 'identifiers', 'stewardship_organisation',
                            'workgroup', 'submitter')

        concept_fields = self._get_concept_fields(concept_class)
        relation_fields = self._get_relation_fields(concept_class)

        included_fields = concept_fields + relation_fields + universal_fields

        # Generate metaclass dynamically
        meta_attrs = {'model': concept_class,
                      'fields': included_fields}
        Meta = type('Meta', tuple(), meta_attrs)

        serializer_attrs = {}
        for field_name in relation_fields:
            if field_name in self.FIELD_SUBSERIALIZER_MAPPING:
                # Field is for something that should have it's component fields serialized
                serializer = self.FIELD_SUBSERIALIZER_MAPPING[field_name]
                serializer_attrs[field_name] = serializer

        serializer_attrs['Meta'] = Meta
        # Generate serializer dynamically
        Serializer = type('Serializer', (BaseSerializer,), serializer_attrs)
        return Serializer

    def _get_class_for_deserializer(self, json):
        data = JSON.loads(json)
        return apps.get_model(data['serialized_model'])

    def generate_deserializer(self, json):
        """ Generate the deserializer """
        concept_model = self._get_class_for_deserializer(json)

        Deserializer = self._generate_serializer_class(concept_model)
        return Deserializer


class Serializer(BaseDjangoSerializer):
    """This is a django serializer that has a 'composed' DRF Serializer inside. """
    data: dict = {}

    def serialize(self, queryset, stream=None, fields=None, use_natural_foreign_keys=False,
                  use_natural_primary_keys=False, progress_output=None, **options):
        concept = queryset[0]

        # Generate the serializer
        ModelSerializer = ConceptSerializerFactory().generate_serializer(concept)

        # Instantiate the serializer
        serializer = ModelSerializer(concept)

        # Add the app label as a key to the json so that the deserializer can be generated
        data = serializer.data
        data['serialized_model'] = concept._meta.label_lower

        self.data = JSON.dumps(data)

    def getvalue(self):
        # Get value must be overridden because django-reversion calls *getvalue* rather than serialize directly
        return self.data


def Deserializer(json, using=DEFAULT_DB_ALIAS, **options):
    # TODO: fix
    """ Deserialize JSON back into Django ORM instances.
        Django deserializers yield a DeserializedObject generator.
        DeserializedObjects are thin wrappers over POPOs. """
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
