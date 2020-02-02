from aristotle_mdr.contrib.serializers.utils import AristotleComponentSerializer
from aristotle_dse.models import (
    DSSClusterInclusion,
    DSSDEInclusion,
    DSSGrouping,
    DistributionDataElementPath,
)

excluded_fields = ('dss',)


class DSSClusterInclusionSerializer(AristotleComponentSerializer):
    class Meta:
        model = DSSClusterInclusion
        exclude = excluded_fields


class DSSDEInclusionSerializer(AristotleComponentSerializer):
    class Meta:
        model = DSSDEInclusion
        exclude = excluded_fields


class DSSGroupingSerializer(AristotleComponentSerializer):
    class Meta:
        model = DSSGrouping
        exclude = excluded_fields


class DistributionDataElementPathSerializer(AristotleComponentSerializer):
    class Meta:
        model = DistributionDataElementPath
        exclude = ('distribution',)
