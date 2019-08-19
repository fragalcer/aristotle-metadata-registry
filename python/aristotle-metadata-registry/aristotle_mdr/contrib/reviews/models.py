from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import pluralize

from model_utils.models import TimeStampedModel

from aristotle_mdr import models as MDR
from aristotle_mdr import perms
from aristotle_mdr.contrib.async_signals.utils import fire

from aristotle_mdr.managers import (
    ReviewRequestQuerySet,
)

from .const import REVIEW_STATES


class StatusMixin:
    @property
    def status_code(self):
        return {x: y for x, y, z in REVIEW_STATES._triples}[self.status]


class ReviewRequest(StatusMixin, TimeStampedModel):
    objects = ReviewRequestQuerySet.as_manager()

    concepts = models.ManyToManyField(
        MDR._concept, related_name="rr_review_requests"
    )
    registration_authority = models.ForeignKey(
        MDR.RegistrationAuthority,
        help_text=_("The registration authority the requester wishes to endorse the metadata item"),
        related_name='rr_requested_reviews',
        on_delete=models.CASCADE
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        help_text=_("The user requesting a review"),
        related_name='rr_requested_reviews',
        on_delete=models.PROTECT
    )
    workgroup = models.ForeignKey(
        MDR.Workgroup,
        help_text=_("A workgroup associated with this review"),
        related_name='rr_workgroup_reviews',
        null=True,
        on_delete=models.SET_NULL
    )
    title = models.TextField(blank=True, null=True, help_text=_("An optional message accompanying a request, this will accompany the approved registration status"))
    status = models.IntegerField(
        choices=REVIEW_STATES,
        default=REVIEW_STATES.open,
        help_text=_('Status of a review')
    )
    target_registration_state = models.IntegerField(
        null=True, blank=True,  # Maybe we dont know what level is appropriate yet?
        choices=MDR.STATES,
        help_text=_("The state at which a user wishes a metadata item to be endorsed")
    )
    registration_date = models.DateField(
        _('Date registration effective'),
        null=True, blank=True,  # Maybe we dont know when it will be registered?
        help_text=_("date and time you want the metadata to be registered from")
    )
    due_date = models.DateField(
        _('Date response required'),
        help_text=_("Date and time a response is required"),
        null=True, blank=True
    )
    cascade_registration = models.IntegerField(
        choices=[(0, _('No')), (1, _('Yes'))],
        default=0,
        help_text=_("Update the registration of associated items")
    )

    @property
    def message(self):
        return self.title

    @property
    def state(self):
        return self.target_registration_state

    @property
    def proposed_supersedes(self):
        """
        Get the proposed supersedes attached to this review only
        """
        return self.supersedes.filter(proposed=True)

    def get_absolute_url(self):
        return reverse(
            "aristotle_reviews:review_details",
            kwargs={'review_id': self.pk}
        )

    def __str__(self):
        return "Review of {count} item{item_pluralise} in {ra} registration authority".format(
            count=self.concepts.count(),
            item_pluralise=pluralize(self.concepts.count()),
            ra=self.registration_authority,
        )

    def is_open(self):
        return self.status == REVIEW_STATES.open

    def can_view(self, user):
        return perms.user_can_view_review(user, self)

    def can_edit(self, user):
        return perms.user_can_edit_review(user, self)

    def timeline(self):
        comments = self.comments.all()
        endorsements = self.endorsements.all()
        state_changes = self.state_changes.all()
        from itertools import chain
        wall = list(chain(comments, endorsements, state_changes))
        wall.sort(key=lambda x: x.created)
        return wall


class ReviewComment(TimeStampedModel):
    class Meta:
        ordering = ['created']

    timeline_type = "comment"

    request = models.ForeignKey(ReviewRequest, related_name='comments', on_delete=models.CASCADE)
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    @property
    def edited(self):
        return self.created != self.modified

    def can_view(self, user):
        return perms.user_can_view_review(user, self)

    def can_edit(self, user):
        return perms.user_can_edit_review(user, self)


class ReviewStatusChangeTimeline(StatusMixin, TimeStampedModel):
    class Meta:
        ordering = ['created']

    timeline_type = "status_change"

    request = models.ForeignKey(ReviewRequest, related_name='state_changes', on_delete=models.CASCADE)
    status = models.IntegerField(
        choices=REVIEW_STATES,
        default=REVIEW_STATES.open,
        help_text=_('Status of a review')
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, on_delete=models.PROTECT
    )

    def can_view(self, user):
        return perms.user_can_view_review(user, self)

    def can_edit(self, user):
        return False


class ReviewEndorsementTimeline(TimeStampedModel):
    class Meta:
        ordering = ['created']

    timeline_type = "endorsement"

    request = models.ForeignKey(ReviewRequest, related_name='endorsements', on_delete=models.CASCADE)
    registration_state = models.IntegerField(
        choices=MDR.STATES,
        help_text=_("The state at which a user wishes a metadata item to be endorsed")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, on_delete=models.PROTECT
    )

    def can_view(self, user):
        return perms.user_can_view_review(user, self)

    def can_edit(self, user):
        return False


@receiver(post_save, sender=ReviewRequest)
def review_request_created(sender, instance, *args, **kwargs):
    if kwargs.get('created'):
        fire("action_signals.review_request_created", obj=instance, **kwargs)
    else:
        fire("action_signals.review_request_updated", obj=instance, **kwargs)
