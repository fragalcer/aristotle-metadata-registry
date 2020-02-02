from aristotle_mdr.contrib.serializers.utils import AristotleComponentSerializer
from aristotle_mdr.models import (
    SupplementaryValue,
    PermissibleValue,
    ValueMeaning,
    DedInputsThrough,
    DedDerivesThrough,
)
from aristotle_mdr.contrib.links.models import RelationRole


class PermissibleValueSerializer(AristotleComponentSerializer):

    class Meta:
        model = PermissibleValue
        fields = ['value', 'meaning', 'order', 'start_date', 'end_date', 'id']


class SupplementaryValueSerializer(AristotleComponentSerializer):

    class Meta:
        model = SupplementaryValue
        fields = ['value', 'meaning', 'order', 'start_date', 'end_date', 'id']


class ValueMeaningSerializer(AristotleComponentSerializer):

    class Meta:
        model = ValueMeaning
        exclude = ('conceptual_domain',)


class DedInputsThroughSerializer(AristotleComponentSerializer):

    class Meta:
        model = DedInputsThrough
        exclude = ('data_element_derivation',)


class DedDerivesThroughSerializer(AristotleComponentSerializer):

    class Meta:
        model = DedDerivesThrough
        exclude = ('data_element_derivation',)


class RelationRoleSerializer(AristotleComponentSerializer):

    class Meta:
        model = RelationRole
        exclude = ('relation',)
