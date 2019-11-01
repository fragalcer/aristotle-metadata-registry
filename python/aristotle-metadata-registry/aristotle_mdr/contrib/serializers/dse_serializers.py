from aristotle_mdr.contrib.serializers.utils import SubSerializer
from aristotle_dse.models import (
    DSSClusterInclusion,
    DSSDEInclusion,
    DSSGrouping,
    DistributionDataElementPath,
)

excluded_fields = ('dss',)


class DSSClusterInclusionSerializer(SubSerializer):
    class Meta:
        model = DSSClusterInclusion
        exclude = excluded_fields


class DSSDEInclusionSerializer(SubSerializer):
    class Meta:
        model = DSSDEInclusion
        exclude = excluded_fields


class DSSGroupingSerializer(SubSerializer):
    class Meta:
        model = DSSGrouping
        exclude = excluded_fields


class DistributionDataElementPathSerializer(SubSerializer):
    class Meta:
        model = DistributionDataElementPath
        exclude = ('distribution',)
