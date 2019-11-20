from django import forms
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.forms import ModelForm, BooleanField

from aristotle_mdr.widgets.bootstrap import BootstrapDateTimePicker
import aristotle_mdr.models as MDR
from aristotle_mdr.forms.creation_wizards import UserAwareForm
from aristotle_mdr.forms.fields import ReviewChangesChoiceField, MultipleEmailField
from aristotle_mdr.contrib.autocomplete import widgets
from django_jsonforms.forms import JSONSchemaField
from aristotle_mdr.forms.utils import RegistrationAuthorityMixin


import logging

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class ChangeStatusGenericForm(RegistrationAuthorityMixin, UserAwareForm):
    state = forms.ChoiceField(choices=MDR.STATES, widget=forms.RadioSelect)
    registrationDate = forms.DateField(
        required=False,
        label=_("Registration date"),
        widget=BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
        initial=timezone.now()
    )
    cascadeRegistration = forms.ChoiceField(
        initial=0,
        choices=[(0, _('No - only register the selected item')), (1, _('Yes - register the selected item, and all child items'))],
        label=_("Do you want to request a status change for associated items")
    )
    changeDetails = forms.CharField(
        max_length=512,
        required=True,
        label=_("Administrative Note"),
        widget=forms.Textarea
    )
    registrationAuthorities = forms.ChoiceField(
        label="Registration Authorities",
        choices=MDR.RegistrationAuthority.objects.none(),
        widget=forms.RadioSelect
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_registration_authority_field(
            field_name="registrationAuthorities", qs=self.user.profile.registrarAuthorities.filter(active=0)
        )


class ChangeStatusForm(ChangeStatusGenericForm):

    def clean_cascadeRegistration(self):
        return self.cleaned_data['cascadeRegistration'] == "1"

    def clean_registrationAuthorities(self):
        value = self.cleaned_data['registrationAuthorities']
        return [
            MDR.RegistrationAuthority.objects.get(id=int(value))
        ]

    def clean_state(self):
        state = self.cleaned_data['state']
        state = int(state)
        MDR.STATES[state]
        return state


class ReviewChangesForm(forms.Form):

    def __init__(self, queryset, static_content, ra, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_list'] = ReviewChangesChoiceField(
            queryset=queryset,
            static_content=static_content,
            ra=ra,
            user=user,
            label=_("Select the items you would like to update")
        )


# Thanks http://stackoverflow.com/questions/6958708/grappelli-to-hide-sortable-field-in-inline-sortable-django-admin
class PermissibleValueForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Meta:
        model = MDR.PermissibleValue
        fields = "__all__"


class CompareConceptsForm(forms.Form):
    item_a = forms.ModelChoiceField(
        queryset=MDR._concept.objects.none(),
        empty_label="None",
        label=_("First item"),
        required=True,
        widget=widgets.ConceptAutocompleteSelect()
    )
    item_b = forms.ModelChoiceField(
        queryset=MDR._concept.objects.none(),
        empty_label="None",
        label=_("Second item"),
        required=True,
        widget=widgets.ConceptAutocompleteSelect()
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.qs = kwargs.pop('qs').visible(self.user)
        super().__init__(*args, **kwargs)

        self.fields['item_a'] = forms.ModelChoiceField(
            queryset=self.qs,
            empty_label="None",
            label=_("First item"),
            required=True,
            widget=widgets.ConceptAutocompleteSelect()
        )
        self.fields['item_b']=forms.ModelChoiceField(
            queryset=self.qs,
            empty_label="None",
            label=_("Second item"),
            required=True,
            widget=widgets.ConceptAutocompleteSelect()
        )


class EditUserForm(ModelForm):
    profile_picture = MDR.PossumProfile._meta.get_field('profilePicture').formfield()

    class Meta:
        model = get_user_model()
        fields = ('email', 'full_name', 'short_name')
        labels = {
            'short_name': 'Display Name'
        }


class EditStatusForm(ModelForm):
    class Meta:
        model = MDR.Status
        fields = ['registrationDate', 'until_date', 'state', 'changeDetails']

    registrationDate = forms.DateField(
        required=False,
        label=_("Registration date"),
        widget=BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
    )
    until_date = forms.DateField(
        required=False,
        label=_("Expiration date"),
        widget=BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"}),
    )
    state = forms.ChoiceField(
        choices=MDR.STATES,
        widget=forms.RadioSelect,
    )
    changeDetails = forms.CharField(
        max_length=512,
        required=True,
        label=_("Administrative note"),
        widget=forms.Textarea
    )
    change_message = forms.CharField(
        max_length=512,
        required=False,
        label=_("Change message"),
        widget=forms.Textarea
    )


class NotificationPermissionsForm(forms.Form):
    notifications_json = JSONSchemaField(
        schema={
            "type": "object",
            "title": "Notification Permissions",
            "properties": {
                "metadata changes": {
                    "type": "object",
                    "title": "Metadata Changes",
                    "properties": {
                        "general changes": {
                            "type": "object",
                            "title": "General Changes",
                            "description": "Notify me of changes to:",
                            "properties": {
                                "items in my workgroups": {
                                    "title": "items in my workgroups",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                },
                                "items I have tagged / favourited": {
                                    "title": "items I have tagged / favourited",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                },
                                "any items I can edit": {
                                    "title": "any items I can edit",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                }
                            }
                        },
                        "superseded": {
                            "type": "object",
                            "title": "Supersedes",
                            "description": "Notify me when the following metadata is superseded:",
                            "properties": {
                                "items in my workgroups": {
                                    "title": "items in my workgroups",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                },
                                "items I have tagged / favourited": {
                                    "title": "items I have tagged / favourited",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                },
                                "any items I can edit": {
                                    "title": "any items I can edit",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                }
                            }
                        },
                        "new items": {
                            "type": "object",
                            "title": "New Items",
                            "description": "Notify me of new items in my workgroups:",
                            "properties": {
                                "new items in my workgroups": {
                                    "title": "new items in my workgroups",
                                    "type": "boolean",
                                    "format": "checkbox",
                                    "default": True
                                }
                            }
                        }
                    }
                },
                "registrar": {
                    "type": "object",
                    "title": "Registrar",
                    "properties": {
                        "item superseded": {
                            "title": "item superseded",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "item registered": {
                            "title": "item registered",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "item changed status": {
                            "title": "item changed status",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "review request created": {
                            "title": "review request created",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "review request updated": {
                            "title": "review request updated",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        }
                    }
                },
                "issues": {
                    "type": "object",
                    "title": "Issues",
                    "description": "Notify me of any updates concerning:",
                    "properties": {
                        "items in my workgroups": {
                            "title": "issues of items in my workgroups",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "items I have tagged / favourited": {
                            "title": "issues of items I have tagged / favourited",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "any items I can edit": {
                            "title": "issues of any items I can edit",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        }
                    }
                },
                "discussions": {
                    "type": "object",
                    "title": "Discussions",
                    "description": "Notify me of activity related to discussions:",
                    "properties": {
                        "new posts": {
                            "title": "new posts",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        },
                        "new comments": {
                            "title": "new comments",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        }
                    }
                },
                "notification methods": {
                    "type": "object",
                    "title": "Notification Methods",
                    "description": "Notify me using the following methods:",
                    "properties": {
                        "email": {
                            "title": "Email",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": False
                        },
                        "within aristotle": {
                            "title": "Within Aristotle",
                            "type": "boolean",
                            "format": "checkbox",
                            "default": True
                        }
                    }
                }
            }
        },
        options={
            'theme': 'bootstrap3',
            'disable_properties': True,
            'disable_collapse': True,
            'disable_edit_json': True,
            'no_additional_properties': True
        },
        label=''
    )


class ShareLinkForm(forms.Form):
    emails = MultipleEmailField(required=False)
    notify_new_users_checkbox = BooleanField(label="Send an email notifying newly invited users", initial=True, required=False)


class ReportingToolForm(forms.Form):

    ra = forms.ModelChoiceField(
        queryset=MDR.RegistrationAuthority.objects.all(),
        label="Registration Authority",
        empty_label=None,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    status = forms.ChoiceField(
        label="Status",
        choices=MDR.STATES,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
