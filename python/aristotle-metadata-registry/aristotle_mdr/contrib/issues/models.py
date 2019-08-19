from django.db import models
from django.conf import settings
from django.db.models.signals import post_save, post_delete, pre_save
from django.core.exceptions import FieldDoesNotExist
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel
from model_utils import Choices
from aristotle_mdr.fields import ConceptForeignKey
from aristotle_mdr.models import _concept
from aristotle_mdr.utils import (url_slugify_issue)
from aristotle_mdr.contrib.async_signals.utils import fire
from ckeditor_uploader.fields import RichTextUploadingField as RichTextField
from jsonfield import JSONField

import logging
logger = logging.getLogger(__name__)


class Issue(TimeStampedModel):

    # Fields on a concept that are proposable (must be text)
    proposable_fields = Choices(
        ('name', _('Name')),
        ('definition', _('Definition')),
        ('references', _('References')),
        ('origin', _('Origin')),
        ('comments', _('Comments')),
    )

    name = models.CharField(max_length=1000)
    description = models.TextField(blank=True)
    item = ConceptForeignKey(
        _concept,
        related_name='issues',
        on_delete=models.CASCADE
    )
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='issues',
        on_delete=models.PROTECT
    )
    isopen = models.BooleanField(default=True)
    proposal_field = models.TextField(
        choices=proposable_fields,
        blank=True
    )
    proposal_value = models.TextField(blank=True)

    labels = models.ManyToManyField(
        'IssueLabel',
        blank=True,
    )

    def can_edit(self, user):
        return user.id == self.submitter.id

    def can_view(self, user):
        return self.item.can_view(user)

    def can_alter_open(self, user):
        return self.can_edit(user) or self.item.can_edit(user)

    def apply(self):
        """Apply proposed changes to an item"""
        if self.proposal_field and self.proposal_value:
            item = self.item
            setattr(item, self.proposal_field, self.proposal_value)
            return item.save()
        return None

    def close(self):
        """Closes an issue, applying changes to item aswell"""
        self.isopen = False
        self.apply()
        return self.save()

    def get_absolute_url(self):
        return url_slugify_issue(self)

    @classmethod
    def get_propose_fields(cls):
        """
        Return list of field names and whether fields are html
        for proposable fields
        """
        fields = []

        for fname, uname in cls.proposable_fields:
            try:
                field = _concept._meta.get_field(fname)
            except FieldDoesNotExist:
                field = None

            if field:
                html = False
                if issubclass(type(field), RichTextField):
                    html = True

                fields.append({
                    'name': fname,
                    'html': html
                })
        return fields

    def __str__(self):
        return self.name


class IssueComment(TimeStampedModel):

    issue = models.ForeignKey(
        Issue,
        related_name='comments',
        on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='issue_comments',
        on_delete=models.PROTECT
    )
    body = models.TextField()

    def can_view(self, user):
        return self.issue.item.can_view(user)

    def can_edit(self, user):
        return user.id == self.author.id


class IssueLabel(models.Model):
    class Meta:
        ordering=["label"]

    label = models.CharField(max_length=200)
    stewardship_organisation = models.ForeignKey(
        'aristotle_mdr.StewardOrganisation',
        null=True, blank=True, default=None,
        on_delete=models.CASCADE,
        to_field="uuid"
    )
    description = models.TextField(blank=True)


@receiver(post_save, sender=Issue)
def new_issue_created(sender, instance, *args, **kwargs):
    # issue = kwargs['instance']
    if kwargs.get('created'):
        fire("concept_changes.issue_created", obj=instance, **kwargs)


@receiver(post_save, sender=IssueComment)
def new_issue_comment_created(sender, instance, *args, **kwargs):
    # issue_comment = kwargs['instance']
    if kwargs.get('created'):
        fire("concept_changes.issue_commented", obj=instance, **kwargs)
