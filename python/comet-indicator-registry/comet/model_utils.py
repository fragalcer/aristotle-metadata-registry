from django.db import models
from aristotle_mdr.fields import ConceptForeignKey


class IndicatorFrameworkDimensionsThrough(models.Model):
    """
    Class representation of the through table between Indicator objects and FrameworkDimension objects.
    The purpose of this table is to specify a `to_field` attribute for the frameworkdimension Foreign Key field,
    in order to use UUID instead of id.
    """
    indicator = ConceptForeignKey(
        "Indicator",
        on_delete=models.CASCADE
    )
    frameworkdimension = models.ForeignKey(
        "FrameworkDimension",
        blank=True,
        to_field='id',
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ('indicator', 'frameworkdimension')
