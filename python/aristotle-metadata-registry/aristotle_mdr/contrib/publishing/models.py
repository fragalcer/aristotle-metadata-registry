from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

import reversion.models

from model_utils.models import TimeStampedModel

from aristotle_mdr.constants import visibility_permission_choices as VISIBILITY_PERMISSION_CHOICES
from aristotle_mdr.managers import UtilsManager


class VersionPublicationRecord(TimeStampedModel):
    class Meta:
        unique_together = (
            ("content_type", "object_id"),
        )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    public_user_publication_date = models.DateTimeField(
        default=None,
        blank=True,
        null=True,
        help_text=_("Date from which public users can view version histories for this item."),
        verbose_name=_("Public version history start date")
    )
    authenticated_user_publication_date = models.DateTimeField(
        default=None,
        blank=True,
        null=True,
        help_text=_("Date from which logged in users can view version histories for this item."),
        verbose_name=_("Logged-in version history start date")
    )


class VersionPermissions(TimeStampedModel):
    objects = UtilsManager()

    version = models.OneToOneField(
        reversion.models.Version,
        on_delete=models.CASCADE,
        primary_key=True)

    visibility = models.IntegerField(
        choices=VISIBILITY_PERMISSION_CHOICES,
        default=VISIBILITY_PERMISSION_CHOICES.workgroup)

    def __str__(self):
        return "Version is: {}  and permissions are: {}".format(str(self.version), str(self.visibility))

    @property
    def id(self):
        return self.version.id


class PublicationRecord(TimeStampedModel):
    class Meta:
        unique_together = (
            ("content_type", "object_id"),
        )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id', for_concrete_model=False)
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="published_content",
        on_delete=models.PROTECT
    )
    permission = models.IntegerField(
        choices=VISIBILITY_PERMISSION_CHOICES,
        default=VISIBILITY_PERMISSION_CHOICES.public
    )
    publication_date = models.DateField(
        default=timezone.now,
        help_text=_("Enter a date in the future to specify the date is published from.")
    )

    def __str__(self):
        return "Published: {} ({}) on {}".format(
            # self.get_reference_type_display().title(),
            self.content_object,
            self.content_object.pk,
            self.publication_date
        )
