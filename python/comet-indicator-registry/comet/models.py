from __future__ import unicode_literals
from typing import List

from django.db import models
from django.db.models import Subquery
from django.utils.translation import ugettext as _

from mptt.models import MPTTModel, TreeForeignKey
from model_utils.models import TimeStampedModel

import aristotle_mdr.models as MDR
import aristotle_dse.models as aristotle_dse
from aristotle_mdr.fields import ConceptForeignKey, ConceptManyToManyField
from aristotle_mdr.utils import (
    fetch_aristotle_settings,
)
from aristotle_mdr.utils.model_utils import (
    aristotleComponent,
)
from comet.managers import FrameworkDimensionManager
from comet.model_utils import IndicatorFrameworkDimensionsThrough


class Framework(MDR.concept):
    template = "comet/framework.html"
    clone_warning_template = "comet/clone_warning/framework.html"
    serialize_weak_entities = [
        ('dimensions', 'frameworkdimension_set'),
    ]

    def root_dimensions(self):
        return self.frameworkdimension_set.all().filter(
            parent=None
        )


class FrameworkDimension(MPTTModel, TimeStampedModel, aristotleComponent):
    parent_field_name = 'framework'

    objects = FrameworkDimensionManager()
    framework = ConceptForeignKey(Framework, on_delete=models.CASCADE)
    name = models.CharField(max_length=2048)
    description = MDR.RichTextField(blank=True)
    parent = TreeForeignKey(
        'self',
        null=True,
        blank=True,
        to_field='id',
        related_name='child_dimensions',
        on_delete=models.CASCADE,
    )

    class MPTTMeta:
        order_insertion_by = ['name']

    @property
    def parentItem(self):
        return self.framework

    def __str__(self):
        return self.name


class OutcomeArea(MDR.concept):
    template = "comet/outcomearea.html"


class QualityStatement(MDR.concept):
    template = "comet/qualitystatement.html"

    institutional_environment = MDR.RichTextField(blank=True)
    timeliness = MDR.RichTextField(blank=True)
    accessibility = MDR.RichTextField(blank=True)
    interpretability = MDR.RichTextField(blank=True)
    relevance = MDR.RichTextField(blank=True)
    accuracy = MDR.RichTextField(blank=True)
    coherence = MDR.RichTextField(blank=True)


class Indicator(MDR.concept):
    """
    An indicator is a single measure that is reported on regularly
    and that provides relevant and actionable information about population or system performance.
    """
    # Subclassing from DataElement causes indicators to present as DataElements, which isn't quite right.
    template = "comet/indicator.html"
    through_edit_excludes = ['dimensions']  # Exclude dimensions from the Indicator editor page.
    backwards_compatible_fields = ['representation_class']

    outcome_areas = ConceptManyToManyField(OutcomeArea, related_name="indicators", blank=True)

    computation_description = MDR.RichTextField(blank=True)
    computation = MDR.RichTextField(blank=True)

    numerator_description = MDR.RichTextField(blank=True)
    denominator_description = MDR.RichTextField(blank=True)
    disaggregation_description = MDR.RichTextField(blank=True)

    quality_statement = ConceptForeignKey(
        QualityStatement,
        null=True, blank=True, on_delete=models.SET_NULL,
        help_text=_("A statement of multiple quality dimensions for the purpose of assessing the quality of the data for reporting against this Indicator.")
    )
    rationale = MDR.RichTextField(blank=True)
    benchmark = MDR.RichTextField(blank=True)
    reporting_information = MDR.RichTextField(blank=True)
    dimensions = ConceptManyToManyField(FrameworkDimension, related_name="indicators", blank=True, through=IndicatorFrameworkDimensionsThrough)

    serialize_weak_entities = [
        ('numerators', 'indicatornumeratordefinition_set'),
        ('denominators', 'indicatordenominatordefinition_set'),
        ('disaggregators', 'indicatordisaggregationdefinition_set'),
    ]
    clone_fields = ['indicatornumeratordefinition', 'indicatordenominatordefinition', 'indicatordisaggregationdefinition']

    @property
    def relational_attributes(self):
        rels = {
            "indicator_sets": {
                "all": _("Indicator Sets that include this Indicator"),
                "qs": IndicatorSet.objects.filter(indicatorinclusion__indicator=self)
            },
        }

        if "aristotle_dse" in fetch_aristotle_settings().get('CONTENT_EXTENSIONS'):
            from aristotle_dse.models import DataSetSpecification, Dataset

            numdefn_datasets = IndicatorNumeratorDefinition.objects.filter(indicator_id=self.id).values('data_set_id')
            dendefn_datasets = IndicatorDenominatorDefinition.objects.filter(indicator_id=self.id).values('data_set_id')
            dissagedefn_datasets = IndicatorDisaggregationDefinition.objects.filter(indicator_id=self.id).values('data_set_id')
            datasets = Dataset.objects.filter(
                id__in=Subquery(
                    numdefn_datasets.union(dendefn_datasets).union(dissagedefn_datasets)
                )
            )

            rels.update({
                "data_sources": {
                    "all": _("Data Sets that are used in this Indicator"),
                    "qs": datasets
                },
            })
        return rels

    @property
    def numerators(self):
        return MDR.DataElement.objects.filter(
            indicatornumeratordefinition__indicator=self
        )

    @property
    def denominators(self):
        return MDR.DataElement.objects.filter(
            indicatordenominatordefinition__indicator=self
        )

    @property
    def disaggregators(self):
        return MDR.DataElement.objects.filter(
            indicatordisaggregationdefinition__indicator=self
        )

    def add_numerator(self, **kwargs):
        self.add_component(model_class=IndicatorNumeratorDefinition, **kwargs)

    def add_denominator(self, **kwargs):
        self.add_component(model_class=IndicatorDenominatorDefinition, **kwargs)

    def add_disaggregator(self, **kwargs):
        self.add_component(model_class=IndicatorDisaggregationDefinition, **kwargs)

    def add_component(self, model_class, **kwargs):
        kwargs.pop('indicator', None)
        from django.db.models import Max
        max_order = list(
            model_class.objects.filter(indicator=self)
            .annotate(latest=Max('order')).values_list('order', flat=True)
        )
        if not max_order:
            order = 1
        else:
            order = max_order[0] + 1
        return model_class.objects.create(indicator=self, order=order, **kwargs)


class IndicatorDataElementBase(aristotleComponent):

    indicator = ConceptForeignKey(Indicator, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(
        "Order",
        help_text=_("The position of this data element in the indicator")
    )
    guide_for_use = MDR.RichTextField(blank=True)
    data_element = ConceptForeignKey(MDR.DataElement, blank=True, null=True, on_delete=models.SET_NULL)
    data_set_specification = ConceptForeignKey(aristotle_dse.DataSetSpecification, blank=True, null=True, on_delete=models.SET_NULL)
    data_set = ConceptForeignKey(aristotle_dse.Dataset, blank=True, null=True, on_delete=models.SET_NULL)
    description = MDR.RichTextField(blank=True)

    inline_field_layout = 'list'

    parent_field_name = 'indicator'

    # Provide a specific field ordering for the advanced metadata editor.
    inline_field_order: List[str] = [
        "data_element",
        "data_set_specification",
        "data_set",
        "description",
        "guide_for_use",
        "order",
    ]

    @property
    def inline_editor_description(self):
        fields = []
        if self.data_element:
            fields.append(f'Data element: {self.data_element.name}')
        if self.data_set_specification:
            fields.append(f'Data set specification: {self.data_set_specification}')
        if self.data_set:
            fields.append(f'Data set: {self.data_set}')

        return fields

    class Meta:
        abstract = True
        ordering = ['order']


class IndicatorNumeratorDefinition(IndicatorDataElementBase):
    class Meta:
        verbose_name = "Numerator"


class IndicatorDenominatorDefinition(IndicatorDataElementBase):
    class Meta:
        verbose_name = "Denominator"


class IndicatorDisaggregationDefinition(IndicatorDataElementBase):
    class Meta:
        verbose_name = "Disaggregator"


class IndicatorSet(MDR.concept):
    template = "comet/indicatorset.html"
    serialize_weak_entities = [
        ('indicators', 'indicatorinclusion_set'),
    ]
    clone_fields = ['indicatorinclusion']

    @property
    def relational_attributes(self):
        rels = {
            "outcome_areas": {
                "all": _("Outcome areas for Indicators in this Indicator Set"),
                "qs": OutcomeArea.objects.filter(indicators__indicatorinclusion__indicator_set=self)
            },
        }
        return rels


class IndicatorInclusion(aristotleComponent):
    order = models.PositiveSmallIntegerField(
        "Order",
        help_text=_("The position of this indicator in the set")
    )
    indicator_set = ConceptForeignKey(IndicatorSet, on_delete=models.CASCADE)
    indicator = ConceptForeignKey(Indicator, blank=True, null=True, on_delete=models.SET_NULL)
    name = models.CharField(
        max_length=1024, blank=True,
        help_text=_("The name identifying this indicator in the set")
    )
    parent_field_name = 'indicator_set'

    class Meta:
        ordering = ['order']
