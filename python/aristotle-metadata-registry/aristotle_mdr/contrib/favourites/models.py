from django.db import models
from aristotle_mdr.models import _concept, PossumProfile


class Tag(models.Model):
    """
    A tag users can assign to metadata items
    These are only viewable and editable by the user that created them
    """

    class Meta:
        unique_together = ('profile', 'name')

    profile = models.ForeignKey(
        PossumProfile,
        related_name='tags',
        on_delete=models.PROTECT
    )
    name = models.CharField(
        max_length=200,
        blank=True
    )
    description = models.TextField(
        blank=True
    )
    created = models.DateTimeField(
        auto_now_add=True
    )
    # Whether this is a "primary" tag or not
    # primary tag denote the item as "favourited" in the ui
    primary = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.name

    def can_view(self, user):
        return user.profile == self.profile

    def can_edit(self, user):
        return self.can_view(user)


class Favourite(models.Model):

    class Meta:
        unique_together = ('tag', 'item')

    tag = models.ForeignKey(
        Tag,
        related_name='favourites', on_delete=models.CASCADE
    )
    item = models.ForeignKey(
        _concept,
        related_name='favourites', on_delete=models.CASCADE
    )
    created = models.DateTimeField(
        auto_now_add=True
    )
