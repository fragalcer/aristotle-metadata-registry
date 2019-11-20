from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.db.models import BLANK_CHOICE_DASH

import aristotle_mdr.models as MDR
from aristotle_mdr.forms.creation_wizards import UserAwareModelForm, UserAwareForm
from aristotle_mdr.forms.forms import ChangeStatusGenericForm

from aristotle_mdr.forms.bulk_actions import LoggedInBulkActionForm, RedirectBulkActionMixin
from aristotle_mdr.widgets.bootstrap import BootstrapDateTimePicker
from aristotle_mdr.contrib.autocomplete.widgets import (
    ConceptAutocompleteSelectMultiple,
    ConceptAutocompleteSelect
)
from aristotle_mdr.widgets.widgets import DataAttrSelect

from . import models

import logging
logger = logging.getLogger(__name__)


class RequestReviewForm(ChangeStatusGenericForm):

    due_date = forms.DateField(
        required=False,
        label=_("Due date"),
        widget=BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
        initial=timezone.now()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_registration_authority_field(
            field_name='registrationAuthorities'
        )

    def clean_registrationAuthorities(self):
        value = self.cleaned_data['registrationAuthorities']
        return MDR.RegistrationAuthority.objects.get(id=int(value))


class RequestReviewCreateForm(UserAwareModelForm):
    class Meta:
        model = models.ReviewRequest
        fields = [
            'title', 'registration_authority', 'due_date', 'target_registration_state',
            'registration_date', 'concepts',
            'cascade_registration'
        ]
        widgets = {
            'title': forms.Textarea(attrs={"rows": "1"}),
            'target_registration_state': forms.Select,
            'due_date': BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
            'registration_date': BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
            'concepts': ConceptAutocompleteSelectMultiple(),
            'cascade_registration': forms.RadioSelect(),
        }
        help_texts = {
            'target_registration_state': "The state for endorsement for metadata in this review",
            'due_date': "Date this review needs to be actioned by",
            'registration_date': "Date the metadata will be endorsed at",
            'title': "A short title for this review",
            'concepts': "List of metadata for review",
            'cascade_registration': "Include related items when registering metadata. When enabled, see the full list of metadata under the \"impact\" tab.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target_registration_state'].choices = BLANK_CHOICE_DASH + MDR.STATES
        self.fields['concepts'].queryset = self.fields['concepts'].queryset.all().visible(self.user)
        self.fields['concepts'].widget.choices = self.fields['concepts'].choices
        self.fields['registration_authority'].queryset = self.fields['registration_authority'].queryset.filter(active=0)  # Exclude "inactive" Registration Authorities.
        self.fields['concepts'].label = "Metadata"


class RequestReviewUpdateForm(UserAwareModelForm):
    class Meta:
        model = models.ReviewRequest
        fields = [
            'title', 'due_date', 'target_registration_state', 'registration_date', 'concepts',
            'cascade_registration'
        ]
        widgets = {
            'title': forms.Textarea(),
            'target_registration_state': forms.RadioSelect(),
            'due_date': BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
            'registration_date': BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
            'concepts': ConceptAutocompleteSelectMultiple(),
            'cascade_registration': forms.RadioSelect(),
        }
        help_texts = {
            'target_registration_state': "The state for endorsement for metadata in this review",
            'due_date': "Date this review needs to be actioned by",
            'registration_date': "Date the metadata will be endorsed at",
            'title': "A short title for this review",
            'concepts': "List of metadata for review",
            'cascade_registration': "Include related items when registering metadata. When enabled, see the full list of metadata under the \"impact\" tab.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['target_registration_state'].choices = MDR.STATES
        self.fields['concepts'].queryset = self.fields['concepts'].queryset.all().visible(self.user)
        self.fields['concepts'].widget.choices = self.fields['concepts'].choices
        self.fields['concepts'].label = "Metadata"


class RequestReviewAcceptForm(UserAwareForm):
    status_message = forms.CharField(
        required=False,
        label=_("Status message"),
        help_text=_("Describe why the status is being changed."),
        widget=forms.Textarea
    )
    close_review = forms.ChoiceField(
        initial=1,
        widget=forms.RadioSelect(),
        choices=[(0, _('No')), (1, _('Yes'))],
        label=_("Do you want to close this review?")
    )


class RequestReviewEndorseForm(RequestReviewAcceptForm):
    registration_state = forms.ChoiceField(
        widget=forms.RadioSelect(),
        choices=MDR.STATES,
        label=_("Registration State"),
        help_text="The state for endorsement for metadata in this review",
    )
    registration_date = forms.DateField(
        widget=BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
        label=_("Registration Date"),
    )
    cascade_registration = forms.ChoiceField(
        initial=0,
        choices=[(0, _('No')), (1, _('Yes'))],
        label=_("Do you want to request a status change for associated items")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['close_review'].initial = 0


class RequestCommentForm(UserAwareModelForm):
    class Meta:
        model = models.ReviewComment
        fields = ['body']


class RequestReviewBulkActionForm(RedirectBulkActionMixin, LoggedInBulkActionForm, RequestReviewForm):
    classes="fa-flag"
    action_text = _('Request review')

    @classmethod
    def get_redirect_url(cls, request):
        from urllib.parse import urlencode
        items = request.POST.getlist("items")
        item_ids = MDR._concept.objects.visible(user=request.user).filter(id__in=items).values_list('id', flat=True)
        params = {'items': item_ids}
        return "{}?{}".format(
            reverse("aristotle_reviews:review_create"),
            urlencode(params, True)
        )


class ReviewRequestSupersedesForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        # Make only concepts in the review allowed as newer items
        review_concepts = kwargs.pop('review_concepts', None)
        widget_data = kwargs.pop('widget_data', {})
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if review_concepts:
            self.fields['newer_item'].queryset = review_concepts
            self.fields['newer_item'].widget.data = widget_data
        if user:
            self.fields['older_item'].queryset = MDR._concept.objects.visible(user)

    class Meta:
        fields = ('newer_item', 'older_item', 'message', 'date_effective')
        widgets = {
            'older_item': ConceptAutocompleteSelect(attrs={"class": "form-control"}),
            'message': forms.widgets.TextInput(attrs={"class": "form-control"}),
            'newer_item': DataAttrSelect(attrs={"class": "form-control"}),
            'date_effective': BootstrapDateTimePicker
        }


class ReviewRequestSupersedesFormset(forms.BaseModelFormSet):
    def clean(self):
        super().clean()
        # Map older items to newer items
        supersedes_map = {}
        ids = []
        for form in self.forms:
            # No need to check deleted forms
            if 'DELETE' in form.cleaned_data and not form.cleaned_data['DELETE']:
                if 'newer_item' not in form.cleaned_data.keys():
                    raise forms.ValidationError([{"newer_item": ["Please provide a newer item."]}])
                if 'older_item' not in form.cleaned_data.keys():
                    raise forms.ValidationError([{"older_item": ["Please provide an older item."]}])
                older = form.cleaned_data['older_item']
                newer = form.cleaned_data['newer_item']
                supersedes_map[older.id] = newer.id
                ids.append(older.id)
                ids.append(newer.id)

        # Get all items as their subclasses
        items = MDR._concept.objects.filter(id__in=ids).select_subclasses()
        item_map = {i.id: i for i in items}

        # Make sure items superseding each other are of the same type
        for older, newer in supersedes_map.items():
            if older in item_map and newer in item_map:
                older_class = type(item_map[older])
                newer_class = type(item_map[newer])
                if older_class != newer_class:
                    message = 'Items superseding each other must be of the same type {older} and {newer} are not'.format(
                        older=item_map[older].name,
                        newer=item_map[newer].name
                    )
                    raise forms.ValidationError(message)
