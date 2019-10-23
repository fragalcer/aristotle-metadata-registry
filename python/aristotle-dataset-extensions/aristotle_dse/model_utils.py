from django.db import models
from aristotle_mdr.fields import ConceptForeignKey
from aristotle_mdr.models import ObjectClass


class DSSGroupingLinkedGroupThrough(models.Model):
    """
    Class representation of the through table for the `linked_group` attribute of DSSGrouping objects.
    The purpose of this table is to specify the `to_dssgrouping` and `from_dssgrouping` field attributes
    for the DSSGrouping model, in order to use UUID instead of id.
    """
    to_dssgrouping = models.ForeignKey(
        blank=True,
        null=True,
        to='DSSGrouping',
        to_field='uuid',
        related_name='to_dssgrouping_reverse',
        on_delete=models.CASCADE,
    )
    from_dssgrouping = models.ForeignKey(
        blank=True,
        null=True,
        to='DSSGrouping',
        to_field='uuid',
        related_name='from_dssgrouping_reverse',
        on_delete=models.CASCADE,
    )


class DSSDEInclusionSpecialisationClassesThrough(models.Model):
    """
    Class representation of the through table between DSSDEInclusion objects and ObjectClass objects (contained in the
    `specialisation_classes` class attribute).
    The purpose of this table is to specify a `to_field` attribute in the dssdeinclusion Foreign Key field, in order to
    use UUID instead of id.
    """

    dssdeinclusion = models.ForeignKey(
        blank=True,
        null=True,
        to="DSSDEInclusion",
        to_field='uuid',
        on_delete=models.CASCADE,
    )
    objectclass = ConceptForeignKey(
        blank=True,
        null=True,
        to=ObjectClass,
        on_delete=models.CASCADE,
    )


class DistributionDataElementPathSpecialisationClassesThrough(models.Model):
    """
    Class representation of the through table between DistributionDataElementPath objects and ObjectClass objects
    (contained in the `specialisation_classes` class attribute).
    The purpose of this table is to specify a `to_field` attribute in the dssdeinclusion Foreign Key field, in order to
    use UUID instead of id.
    """

    distributiondataelementpath = models.ForeignKey(
        blank=True,
        null=True,
        to="DistributionDataElementPath",
        to_field='uuid',
        on_delete=models.CASCADE,
    )
    objectclass = ConceptForeignKey(
        blank=True,
        null=True,
        to=ObjectClass,
        on_delete=models.CASCADE,
    )
