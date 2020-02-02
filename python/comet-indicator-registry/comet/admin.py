import comet
from aristotle_mdr.register import register_concept

register_concept(comet.models.IndicatorSet)
register_concept(comet.models.OutcomeArea)

register_concept(
    comet.models.Indicator,
    extra_fieldsets=[
        ('Metadata', {'fields': ['outcome_areas', 'quality_statement']}),
    ],
    reversion={
        'follow': ['indicatornumeratordefinition_set', 'indicatordenominatordefinition_set',
                   'indicatordisaggregationdefinition_set'],
        'follow_classes': [
            comet.models.IndicatorNumeratorDefinition,
            comet.models.IndicatorDenominatorDefinition,
            comet.models.IndicatorDisaggregationDefinition,
        ]
    },
)

register_concept(
    comet.models.QualityStatement,
    extra_fieldsets=[
        ('Data Quality Guidelines',
         {'fields': ['timeliness', 'accessibility', 'interpretability', 'relevance', 'accuracy',
                     'coherence']}
         ),
    ]
)

register_concept(
    comet.models.Framework,
    extra_fieldsets=[
        ('Data Quality Guidelines', {'fields': []}),
    ]
)
