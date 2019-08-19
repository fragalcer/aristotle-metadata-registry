from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

import aristotle_mdr.models as MDR
import aristotle_mdr.widgets.widgets as widgets
from aristotle_mdr.utils import concept_to_clone_dict
from aristotle_mdr.forms.creation_wizards import ConceptForm


def MembershipField(model, name):
    return forms.ModelMultipleChoiceField(
        queryset=model.objects.all(),
        required=False,
        widget=FilteredSelectMultiple(name, False)
    )


class AristotleProfileForm(forms.ModelForm):
    viewer_in = MembershipField(MDR.Workgroup, _('workgroups'))
    steward_in = MembershipField(MDR.Workgroup, _('workgroups'))
    submitter_in = MembershipField(MDR.Workgroup, _('workgroups'))
    workgroup_manager_in = MembershipField(MDR.Workgroup, _('workgroups'))

    organization_manager_in = MembershipField(MDR.Organization, 'organizations')
    registrar_in = MembershipField(MDR.RegistrationAuthority, _('registration authorities'))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        from aristotle_mdr.models import Workgroup

        # if self.instance and self.instance.user.count() == 1: # and self.instance.user.exists():
        try:
            self.fields['registrar_in'].initial = self.instance.user.registrar_in.all()
            self.fields['organization_manager_in'].initial = self.instance.user.organization_manager_in.all()

            self.fields['workgroup_manager_in'].initial = Workgroup.objects.filter(members__user=self.instance.user, members__role="manager").all()
            self.fields['steward_in'].initial = Workgroup.objects.filter(members__user=self.instance.user, members__role="steward").all()
            self.fields['submitter_in'].initial = Workgroup.objects.filter(members__user=self.instance.user, members__role="submitter").all()
            self.fields['viewer_in'].initial = Workgroup.objects.filter(members__user=self.instance.user, members__role="viewer").all()
        except get_user_model().DoesNotExist:
            pass

    def save_memberships(self, user, *args, **kwargs):
        from aristotle_mdr.models import WorkgroupMembership
        WorkgroupMembership.objects.filter(user=user).delete()

        seen_wgs = set()
        memberships = []
        if "workgroup_manager_in" in self.cleaned_data.keys():
            for wg in self.cleaned_data['workgroup_manager_in']:
                if wg.pk not in seen_wgs:
                    memberships.append(WorkgroupMembership(user=user, group=wg, role="manager"))
                seen_wgs.add(wg.pk)
        if "steward_in" in self.cleaned_data.keys():
            for wg in self.cleaned_data['steward_in']:
                if wg.pk not in seen_wgs:
                    memberships.append(WorkgroupMembership(user=user, group=wg, role="steward"))
                seen_wgs.add(wg.pk)
        if "submitter_in" in self.cleaned_data.keys():
            for wg in self.cleaned_data['submitter_in']:
                if wg.pk not in seen_wgs:
                    memberships.append(WorkgroupMembership(user=user, group=wg, role="submitter"))
                seen_wgs.add(wg.pk)
        if "viewer_in" in self.cleaned_data.keys():
            for wg in self.cleaned_data['viewer_in']:
                if wg.pk not in seen_wgs:
                    memberships.append(WorkgroupMembership(user=user, group=wg, role="viewer"))
                seen_wgs.add(wg.pk)
        WorkgroupMembership.objects.bulk_create(memberships)

        if "organization_manager_in" in self.cleaned_data.keys():
            user.organization_manager_in.set(self.cleaned_data['organization_manager_in'])
        if "registrar_in" in self.cleaned_data.keys():
            user.registrar_in.set(self.cleaned_data['registrar_in'])


class AdminConceptForm(ConceptForm):
    # Thanks: http://stackoverflow.com/questions/6034047/one-to-many-inline-select-with-django-admin
    # Although concept is an abstract class, we still need this to have a reverse one-to-many edit field.
    class Meta:
        model = MDR._concept
        fields = "__all__"
        exclude = ["superseded_by_items", "superseded_items"]

    def __init__(self, *args, **kwargs):

        self.request = kwargs.pop('request', None)
        clone = self.request.GET.get("clone", None)
        name_suggest_fields = kwargs.pop('name_suggest_fields', [])
        separator = kwargs.pop('separator', '-')
        if clone:
            item_to_clone = MDR._concept.objects.filter(id=clone).first().item
            kwargs['initial'] = concept_to_clone_dict(item_to_clone)

        super().__init__(*args, **kwargs)
        if self.instance and not clone:
            self.itemtype = self.instance.__class__

        if name_suggest_fields:
            self.fields['name'].widget = widgets.NameSuggestInput(name_suggest_fields=name_suggest_fields, separator=separator)
        self.fields['workgroup'].queryset = self.request.user.profile.editable_workgroups.all()
        # self.fields['workgroup'].initial = self.request.user.profile.activeWorkgroup


class StatusInlineForm(forms.ModelForm):
    registrationAuthority = forms.ModelChoiceField(
        label='Registration Authority',
        queryset=MDR.RegistrationAuthority.objects.filter(active=0),
        widget=widgets.RegistrationAuthoritySelect
    )

    class Meta:
        model = MDR.Status
        fields = "__all__"
