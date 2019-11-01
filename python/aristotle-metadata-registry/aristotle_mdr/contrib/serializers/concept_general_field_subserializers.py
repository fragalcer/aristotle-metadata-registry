from rest_framework import serializers
from aristotle_mdr.models import RecordRelation
from aristotle_mdr.contrib.serializers.utils import SubSerializer
from aristotle_mdr.contrib.custom_fields.models import CustomValue
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.contrib.identifiers.models import ScopedIdentifier


class SlotsSerializer(SubSerializer):
    class Meta:
        model = Slot
        fields = ['name', 'value', 'order', 'permission', 'id']


class CustomValuesSerializer(SubSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = CustomValue
        fields = ['field', 'name', 'content', 'id']

    def get_name(self, custom_value):
        return custom_value.field.name


class IdentifierSerializer(SubSerializer):

    class Meta:
        model = ScopedIdentifier
        fields = ['namespace', 'identifier', 'version', 'order', 'id']


class OrganisationRecordsSerializer(SubSerializer):
    class Meta:
        model = RecordRelation
        fields = ['organization_record', 'type', 'id']
