from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from aristotle_mdr import models as MDR
from aristotle_mdr.fields import (
    ConceptForeignKey,
    ShortTextField,
    ConceptManyToManyField,
)

from aristotle_mdr.managers import PublishedItemQuerySet


class CollectionQuerySet(PublishedItemQuerySet):
    pass


# When we switch to MPTT we will need this
# class CollectionQuerySet(PublishedMixin, TreeQuerySet):
#     pass
# class CollectionManager(models.Manager.from_queryset(PageQuerySet), TreeManager):
#     pass


class Collection(TimeStampedModel):
    """A collection of metadata belonging to a Stewardship Organisation"""
    objects = CollectionQuerySet.as_manager()
    # objects = CollectionManager()

    stewardship_organisation = models.ForeignKey(
        'aristotle_mdr.StewardOrganisation', to_field="uuid", null=False, on_delete=models.CASCADE
    )
    name = ShortTextField(
        help_text=_("The name of the group.")
    )
    description = MDR.RichTextField(
        _('description'),
        blank=True
    )

    metadata = ConceptManyToManyField('aristotle_mdr._concept', blank=True)
    parent_collection = models.ForeignKey('self', blank=True, null=True, on_delete=models.CASCADE)
    publication_details = GenericRelation('aristotle_mdr_publishing.PublicationRecord')

    def get_absolute_url(self):
        return reverse(
            "aristotle_mdr:stewards:group:collection_detail_view",
            args=[self.stewardship_organisation.slug, self.pk]
        )

    def __str__(self):
        return self.name


# class CollectionEntry(models.Model):
#     order = models.PositiveSmallIntegerField("Order")
#     collection = ConceptForeignKey(Collection)
#     metadata = ConceptForeignKey('aristotle_mdr._concept', blank=True, null=True)
