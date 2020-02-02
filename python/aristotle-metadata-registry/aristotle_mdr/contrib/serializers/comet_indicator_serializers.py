from comet import models
from aristotle_mdr.contrib.serializers.utils import AristotleComponentSerializer


class IndicatorNumeratorSerializer(AristotleComponentSerializer):
    class Meta:
        model = models.IndicatorNumeratorDefinition
        exclude = ('indicator',)


class IndicatorDenominatorSerializer(AristotleComponentSerializer):
    class Meta:
        model = models.IndicatorDenominatorDefinition
        exclude = ('indicator',)


class IndicatorDisaggregationSerializer(AristotleComponentSerializer):
    class Meta:
        model = models.IndicatorDisaggregationDefinition
        exclude = ('indicator',)


class IndicatorInclusionSerializer(AristotleComponentSerializer):
    class Meta:
        model = models.IndicatorInclusion
        exclude = ('indicator',)


class FrameworkDimensionSerializer(AristotleComponentSerializer):
    class Meta:
        model = models.FrameworkDimension
        exclude = ('framework',)
