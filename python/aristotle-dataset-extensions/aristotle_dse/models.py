from __future__ import unicode_literals
from typing import List, Tuple, Set, Any
from django.db import models
from django.utils.translation import ugettext as _
from django.conf import settings
from model_utils import Choices
import aristotle_mdr as aristotle
from aristotle_mdr.models import RichTextField
from aristotle_mdr.utils.model_utils import get_comet_indicator_relational_attributes
from aristotle_mdr.fields import (
    ConceptForeignKey,
    ConceptManyToManyField,
    ShortTextField,
)
from aristotle_mdr.structs import Tree, Node
from aristotle_mdr.utils import fetch_aristotle_settings

CARDINALITY = Choices(('optional', _('Optional')), ('conditional', _('Conditional')), ('mandatory', _('Mandatory')))


class DataCatalog(aristotle.models.concept):
    """
    A data catalog is a curated collection of metadata about datasets.
    """
    template = "aristotle_dse/concepts/datacatalog.html"
    issued = models.DateField(
        blank=True, null=True,
        help_text=_('Date of formal issuance (e.g., publication) of the catalog.'),
        )
    dct_modified = models.DateTimeField(
        blank=True, null=True,
        help_text=_('Most recent date on which the catalog was changed, updated or modified.'),
        )
    homepage = models.URLField(
        blank=True, null=True,
        help_text=_('The dataset specification to which this data source conforms'),
        )
    # publisher_record = models.ForeignKey(
    #     aristotle.models.OrganizationRecord,
    #     blank=True, null=True,
    #     help_text=_('The entity responsible for making the catalog online.'),
    #     )
    spatial = models.TextField(
        blank=True, null=True,
        help_text=_('The geographical area covered by the catalog.'),
        )
    license = models.TextField(
        blank=True, null=True,
        help_text=_(
            'This links to the license document under which the catalog is made available and not the datasets. '
            'Even if the license of the catalog applies to all of its datasets and distributions, '
            'it should be replicated on each distribution.'
        ),
        )


class Dataset(aristotle.models.concept):
    """
    A collection of data, published or curated by a single agent, and available
    for access or download in one or more formats.
    """
    template = "aristotle_dse/concepts/dataset.html"

    # Themes = slots with name 'theme'
    # Keywords = slots with name 'keyword'
    issued = models.DateField(
        blank=True, null=True,
        help_text=_('Date of formal issuance (e.g., publication) of the catalog.'),
        )
    # publisher_record = models.ForeignKey(
    #     aristotle.models.OrganizationRecord,
    #     verbose_name=_("Publisher"),
    #     blank=True, null=True,
    #     help_text=_('An entity responsible for making the dataset available.'),
    #     )
    frequency = models.TextField(
        blank=True, null=True,
        help_text=_('The frequency at which dataset is published.'),
        )
    spatial = models.TextField(
        blank=True, null=True,
        help_text=_('Spatial coverage of the dataset.'),
        )
    temporal = models.TextField(
        blank=True, null=True,
        help_text=_('The temporal period that the dataset covers.'),
        )
    catalog = models.ForeignKey(
        DataCatalog,
        blank=True, null=True,
        on_delete=models.SET_NULL,
        help_text=_('An entity responsible for making the dataset available.'),
        )
    landing_page = models.URLField(
        blank=True, null=True,
        help_text=_('A Web page that can be navigated to in a Web browser to gain access to the dataset, its distributions and/or additional information'),
        )
    contact_point = models.TextField(
        blank=True, null=True,
        help_text=_('The temporal period that the dataset covers.'),
        )
    dct_modified = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Modification date",
        help_text=_('Most recent date on which the dataset was changed, updated or modified.'),
        )

    @property
    def relational_attributes(self):
        return get_comet_indicator_relational_attributes(self)


class Distribution(aristotle.models.concept):
    """
    Represents a specific available form of a dataset.
    Each dataset might be available in different forms,
    these forms might represent different formats
    of the dataset or different endpoints.
    Examples of distributions include a downloadable CSV file, an API or an RSS feed
    """
    template = "aristotle_dse/concepts/distribution.html"
    serialize_weak_entities = [
        ('data_elements', 'distributiondataelementpath_set'),
    ]
    issued = models.DateField(
        blank=True, null=True,
        help_text=_('Date of formal issuance (e.g., publication) of the catalog.'),
        )
    dct_modified = models.DateTimeField(
        blank=True, null=True,
        verbose_name="Modification date",
        help_text=_('Most recent date on which the catalog was changed, updated or modified.'),
        )
    dataset = models.ForeignKey(
        Dataset,
        blank=True, null=True,
        on_delete=models.SET_NULL,
        help_text=_('Connects a distribution to its available datasets'),
        )
    license = models.TextField(
        blank=True, null=True,
        help_text=_('This links to the license document under which the distribution is made available.'),
        )
    rights = models.TextField(
        blank=True, null=True,
        help_text=_('Information about rights held in and over the distribution.'),
        )
    access_URL = models.URLField(
        blank=True, null=True,
        help_text=_('A landing page, feed, SPARQL endpoint or other type of resource that gives access to the distribution of the dataset.'),
        )
    download_URL = models.URLField(
        blank=True, null=True,
        help_text=_('A file that contains the distribution of the dataset in a given format.'),
        )
    byte_size = models.TextField(  # Why text? Because CKAN returns ??? Maybe we can clean in the future
        blank=True, null=True,
        help_text=_('The size in bytes can be approximated when the precise size is not known.'),
        )
    media_type = models.CharField(
        blank=True, null=True,
        max_length=512,
        help_text=_('The media type of the distribution as defined by IANA.'),
        )
    format_type = models.CharField(  # renamed from format as python will complain
        blank=True, null=True,
        max_length=512,
        help_text=_('The file format of the distribution.'),
        )


class DistributionDataElementPath(aristotle.models.aristotleComponent):
    class Meta:
        ordering = ['order']
    parent_field_name = 'distribution'

    # TODO: Set this to NOT NULL
    distribution = models.ForeignKey(
        Distribution,
        blank=True, null=True,
        on_delete=models.CASCADE,
        help_text=_('A relation to the DCAT Distribution Record.'),
        )
    data_element = ConceptForeignKey(
        aristotle.models.DataElement,
        blank=True, null=True,
        help_text=_('An entity responsible for making the dataset available.'),
        verbose_name='Data Element',
        on_delete=models.SET_NULL,
        )
    logical_path = models.CharField(
        max_length=256,
        help_text=_("A text expression that specifies how to identify which series of data in the distribution maps to this data element")
        )
    order = models.PositiveSmallIntegerField(
        "Position",
        null=True, blank=True,
        help_text=_("Column position within a dataset.")
        )
    specialisation_classes = ConceptManyToManyField(
        aristotle.models.ObjectClass,
        help_text=_(""),
        blank=True
    )


class DataSetSpecification(aristotle.models.concept):
    r"""
    A collection of :model:`aristotle_mdr.DataElement`\s
    specifying the order and fields required for a standardised
    :model:`aristotle_dse.DataSource`.
    """
    # edit_page_excludes = ['clusters', 'data_elements']
    serialize_weak_entities = [
        ('clusters', 'dssclusterinclusion_set'),
        ('data_elements', 'dssdeinclusion_set'),
        ('groups', 'groups'),
    ]
    clone_fields = ['dssclusterinclusion_set', 'dssdeinclusion_set', 'groups']

    template = "aristotle_dse/concepts/dataSetSpecification.html"

    statistical_unit = ConceptForeignKey(
        aristotle.models._concept,
        on_delete=models.SET_NULL,
        related_name='statistical_unit_of',
        blank=True,
        null=True,
        help_text=_("A Statistical Unit is the Object Class that is recorded against each entry described by this specification"),
        verbose_name='Statistical Unit'
        )
    collection_method = aristotle.models.RichTextField(
        blank=True,
        help_text=_('')
        )

    def addDataElement(self, data_element, **kwargs):
        DSSDEInclusion.objects.get_or_create(
            data_element=data_element,
            dss=self,
            defaults=kwargs
            )

    def addCluster(self, child, **kwargs):
        DSSClusterInclusion.objects.get_or_create(
            child=child,
            dss=self,
            defaults=kwargs
            )

    @property
    def clusters(self):
        """Fetch all child dss's elements on this dss directly"""
        ids = self.dssclusterinclusion_set.all().values_list('child', flat=True)
        return self.__class__.objects.filter(id__in=ids)

    @property
    def data_elements(self):
        """Fetch all included data elements on this dss directly"""
        ids = self.dssdeinclusion_set.all().values_list('data_element', flat=True)
        return aristotle.models.DataElement.objects.filter(id__in=ids)

    @property
    def cluster_inclusions(self):
        """Fetch cluster inclustions (with child pre-fetched)"""
        return self.dssclusterinclusion_set.all().select_related('child')

    @property
    def data_element_inclusions(self):
        """Fetch data elemen inclustions (with de pre-fetched)"""
        return self.dssdeinclusion_set.all().select_related('data_element')

    def ungrouped_data_element_inclusions(self):
        return self.dssdeinclusion_set.filter(group=None)

    @property
    def registry_cascade_items(self):
        return (
            list(self.clusters.all()) +
            list(self.data_elements.all()) +
            list(aristotle.models.ObjectClass.objects.filter(dataelementconcept__dataelement__dssInclusions__dss=self)) +
            list(aristotle.models.Property.objects.filter(dataelementconcept__dataelement__dssInclusions__dss=self)) +
            list(aristotle.models.ValueDomain.objects.filter(dataelement__dssInclusions__dss=self)) +
            list(aristotle.models.DataElementConcept.objects.filter(dataelement__dssInclusions__dss=self))
        )

    def get_download_items(self, cluster_relations=None, de_relations=None):
        from django.db.models import Q

        if not cluster_relations:
            cluster_relations = self.get_all_clusters()
        dss_ids = self.get_unique_ids(cluster_relations)

        if not de_relations:
            de_relations = self.get_de_relations(dss_ids)
        de_ids = self.get_unique_ids(de_relations)

        items = [
            type(self).objects.filter(Q(id__in=dss_ids) & ~Q(id=self.id)).distinct(),
            aristotle.models.DataElement.objects.filter(id__in=de_ids).distinct(),
            aristotle.models.DataElementConcept.objects.filter(dataelement__in=de_ids).distinct(),
            aristotle.models.ObjectClass.objects.filter(dataelementconcept__dataelement__in=de_ids).distinct(),
            aristotle.models.Property.objects.filter(dataelementconcept__dataelement__in=de_ids).distinct(),
            aristotle.models.ValueDomain.objects.filter(dataelement__in=de_ids).distinct(),
        ]

        if 'aristotle_mdr_backwards' in fetch_aristotle_settings().get('CONTENT_EXTENSIONS', []):
            from aristotle_mdr.contrib.aristotle_backwards.models import ClassificationScheme
            items.append(
                ClassificationScheme.objects.filter(valueDomains__dataelement__in=de_ids).distinct(),
            )

        return items

    def get_all_clusters(self) -> List[Tuple[int, int, Any]]:
        """Get all clusters as (parent_id, child_id, inclusion) tuples (depth limited)"""
        # Final triples
        clusters = []
        # Id's of last level
        last_level_ids: Set = set([self.id])
        # Inclusion id's
        seen_inclusions: Set = set()

        for i in range(settings.CLUSTER_DISPLAY_DEPTH):
            # get parent, child tuples
            values = DSSClusterInclusion.objects.filter(
                dss_id__in=last_level_ids,
            ).order_by('order')

            last_level_ids.clear()
            for inc in values:
                if inc.id not in seen_inclusions:
                    # Add to sets
                    seen_inclusions.add(inc.id)
                    last_level_ids.add(inc.child_id)
                    # Add tuple to final list
                    triple = (inc.dss_id, inc.child_id, inc)
                    clusters.append(triple)

            if not last_level_ids:
                break

        return clusters

    def get_de_relations(self, dss_ids: Set[int]) -> List[Tuple[int, int, Any]]:
        """Helper used to fetch all data element relations for a set of dss's"""
        dss_ids.add(self.id)
        values = DSSDEInclusion.objects.filter(
            dss__in=dss_ids,
        ).order_by('order')

        values_list = []
        for inc in values:
            values_list.append(
                (inc.dss_id, inc.data_element_id, inc)
            )

        return values_list

    def get_unique_ids(self, relations: List[Tuple[int, int, Any]]) -> Set[int]:
        unique_ids = set()

        for pair in relations:
            unique_ids.add(pair[0])
            unique_ids.add(pair[1])

        return unique_ids

    def get_cluster_tree(self, cluster_relations, de_relations, objects={}):

        # Lookup all objects
        if not objects:
            dss_ids = self.get_unique_ids(cluster_relations)
            
            de_ids = self.get_unique_ids(de_relations)
            objects = type(self).objects.in_bulk(dss_ids)
            objects.update(aristotle.models.DataElement.objects.in_bulk(de_ids))

        all_relations = cluster_relations + de_relations

        root = Node(data=self)
        tree = Tree(root)

        tree.add_bulk_relations(root, all_relations, objects)

        return tree

    @property
    def relational_attributes(self):
        return get_comet_indicator_relational_attributes(self)


class DSSInclusion(aristotle.models.aristotleComponent):
    class Meta:
        abstract = True
        ordering = ['order']

    inline_field_layout = 'list'
    parent_field_name = 'dss'

    reference = models.CharField(
        max_length=512,
        blank=True,
        help_text=_("Optional field for refering to this item within the DSS."),
        default=''
    )

    dss = ConceptForeignKey(DataSetSpecification, on_delete=models.CASCADE)
    maximum_occurrences = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Maximum Occurrences"),
        help_text=_("The maximum number of times a item can be included in a dataset")
        )
    inclusion = models.CharField(
        "Inclusion",
        choices=CARDINALITY,
        default=CARDINALITY.conditional,
        max_length=20,
        help_text=_("Specifies if a field is required, optional or conditional within a dataset based on this specification.")
        )
    specific_information = RichTextField(
        blank=True,
        help_text=_("Any additional information on the inclusion of a data element or cluster in a dataset.")
        )
    conditional_inclusion = RichTextField(
        "Conditional Inclusion",
        blank=True,
        help_text=_("If an item is present conditionally, this field defines the conditions under which an item will appear.")
        )
    order = models.PositiveSmallIntegerField(
        "Position",
        null=True,
        blank=True,
        help_text=_("If a dataset is ordered, this indicates which position this item is in a dataset.")
        )


class DSSGrouping(aristotle.models.aristotleComponent):
    class Meta:
        ordering = ['order']
        verbose_name = 'DSS Grouping'

    inline_field_layout = 'list'
    parent_field_name = 'dss'

    dss = ConceptForeignKey(DataSetSpecification, related_name="groups", on_delete=models.CASCADE)
    name = ShortTextField(
        help_text=_("The name applied to the grouping.")
    )
    definition = RichTextField(
        _('definition'),
        blank=True,
    )
    linked_group = models.ManyToManyField(
        'self', blank=True, symmetrical=False
    )
    order = models.PositiveSmallIntegerField(
        "Position",
        null=True,
        blank=True,
    )
    parent = 'dss'

    def __str__(self):
        return self.name


# Holds the link between a DSS and a Data Element with the DSS Specific details.
class DSSDEInclusion(DSSInclusion):
    data_element = ConceptForeignKey(aristotle.models.DataElement, related_name="dssInclusions", on_delete=models.CASCADE)
    group = models.ForeignKey(
        DSSGrouping,
        blank=True, null=True,
        on_delete=models.SET_NULL
    )
    specialisation_classes = ConceptManyToManyField(
        aristotle.models.ObjectClass,
        help_text=_(""),
        blank=True,
    )

    inline_field_layout = 'list'
    inline_field_order = [
        "order", "dss",
        "data_element", "reference", "inclusion", "maximum_occurrences",
        "conditional_inclusion", "specific_information", "group", "specialisation_classes"
    ]

    class Meta(DSSInclusion.Meta):
        verbose_name = "DSS Data Element"

    @property
    def include(self):
        return self.data_element

    def inline_editor_description(self):
        if self.group:
            msg = "Data element '%s' in group '%s' at position %s" % (self.data_element.name, self.group.name, self.order)
        else:
            msg = "Data element '%s' at position %s" % (self.data_element.name, self.order)
        return msg

    def __str__(self):
        has_reference = self.reference is not None and self.reference != ''
        if has_reference:
            return 'Data element {} at position {} with reference: {}.'.format(self.data_element_id, self.order, self.reference)
        return 'Data element {} at position {}'.format(self.data_element_id, self.order)

    def get_absolute_url(self):
        pass


# Holds the link between a DSS and a cluster with the DSS Specific details.
class DSSClusterInclusion(DSSInclusion):
    """
    The child in this relationship is considered to be a child of the parent DSS as specified by the `dss` property.
    """
    child = ConceptForeignKey(DataSetSpecification, related_name='parent_dss', on_delete=models.CASCADE)

    inline_field_layout = 'list'
    inline_field_order = [
        "order", "dss", "child",
        "reference", "inclusion", "maximum_occurrences",
        "conditional_inclusion", "specific_information"
    ]

    class Meta(DSSInclusion.Meta):
        verbose_name = "DSS Cluster"

    @property
    def include(self):
        return self.child

    def inline_editor_description(self):
        if self.order:
            return "Cluster '{cls}' at position {pos}".format(cls=self.child.name, pos=self.order)
        return "Cluster '{}'".format(self.child.name)

    def __str__(self):
        return self.inline_editor_description()
