from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.forms.models import inlineformset_factory
from django.utils import timezone, dateparse
from django.utils.translation import ugettext_lazy as _

import aristotle_mdr.models as MDR
from aristotle_mdr.contrib.autocomplete import widgets
from aristotle_mdr.exceptions import NoUserGivenForUserForm
from aristotle_mdr.managers import ConceptQuerySet
from aristotle_mdr.perms import user_can_remove_from_workgroup, user_can_move_to_workgroup
from aristotle_mdr.widgets.bootstrap import BootstrapDateTimePicker
from aristotle_mdr.widgets.widgets import NameSuggestInput
from aristotle_mdr.utils.utils import fetch_aristotle_settings

from aristotle_mdr.contrib.custom_fields.forms import CustomValueFormMixin


# Fields to not show in editors
EXCLUDED_FIELD_NAMES = ['_concept_ptr', 'superseded_by_items', '_is_public', '_is_locked', '_type', 'origin_URI', 'submitter', 'stewardship_organisation']


class UserAwareFormMixin:
    def __init__(self, *args, **kwargs):
        if 'user' in kwargs.keys():
            self.user = kwargs.pop('user')
        elif 'request' in kwargs.keys():
            self.user = kwargs['request'].user
        elif hasattr(self, 'request'):
            self.user = self.request.user
        else:
            raise NoUserGivenForUserForm("The class inheriting from UserAwareForm was not called with a user or request parameter")
        super().__init__(*args, **kwargs)


class UserAwareForm(UserAwareFormMixin, forms.Form):
    pass


class UserAwareModelForm(UserAwareFormMixin, forms.ModelForm):
    class Meta:
        model = MDR._concept
        exclude = EXCLUDED_FIELD_NAMES


class WorkgroupVerificationMixin:
    cant_move_from_permission_error = _("You do not have permission to remove an item from this workgroup.")
    cant_move_to_permission_error = _("You do not have permission to move an item to that workgroup.")

    def clean_workgroup(self):
        new_workgroup = self.cleaned_data['workgroup']
        old_workgroup = self.instance.workgroup

        # If new item return
        if self.instance.pk is None:
            return new_workgroup

        # If old workgroup is None return
        if old_workgroup is None:
            return new_workgroup

        # If workgroup didnt change return
        if old_workgroup == new_workgroup:
            return new_workgroup

        # Check user can remove from old wg
        if not user_can_remove_from_workgroup(self.user, old_workgroup):
            raise forms.ValidationError(self.cant_move_from_permission_error)

        # Check user can move to new wg
        if not user_can_move_to_workgroup(self.user, new_workgroup):
            raise forms.ValidationError(self.cant_move_to_permission_error)

        return new_workgroup


class CheckIfModifiedMixin(forms.ModelForm):
    modified_since_form_fetched_error = _(
        "The object you are editing has been changed, review the changes before continuing then if you wish to save your changes click the Save button below."
    )
    modified_since_field_missing = _(
        "Unable to determine if this save will overwrite an existing save. Please try again. "
    )
    last_fetched = forms.CharField(
        widget=forms.widgets.HiddenInput(),
        initial=timezone.now(),
        required=True,
        error_messages={'required': modified_since_field_missing}
    )

    def __init__(self, *args, **kwargs):
        # Tricky... http://www.avilpage.com/2015/03/django-form-gotchas-dynamic-initial.html
        super().__init__(*args, **kwargs)
        self.initial['last_fetched'] = timezone.now()
        self.fields['last_fetched'].initial = timezone.now()

    def clean_last_fetched(self):
        # We need a UTC version of the modified time
        modified_time = timezone.localtime(self.instance.modified, timezone.utc)
        # And need to parse the submitted time back which is in UTC.
        last_fetched = self.cleaned_data['last_fetched']
        last_fetched = dateparse.parse_datetime(last_fetched)
        self.cleaned_data['last_fetched'] = last_fetched
        if self.cleaned_data['last_fetched'] is None or self.cleaned_data['last_fetched'] == "":
            self.initial['last_fetched'] = timezone.now()
            raise forms.ValidationError(CheckIfModifiedMixin.modified_since_field_missing)
        if modified_time > self.cleaned_data['last_fetched']:
            self.initial['last_fetched'] = timezone.now()
            raise forms.ValidationError(CheckIfModifiedMixin.modified_since_form_fetched_error)


class ConceptForm(WorkgroupVerificationMixin, UserAwareModelForm):
    """
    Add this in when we look at reintroducing the fancy templates.
    required_css_class = 'required'
    """

    def __init__(self, *args, **kwargs):
        from comet.managers import FrameworkDimensionQuerySet
        # TODO: Have this throw a 'no user' error
        super().__init__(*args, **kwargs)

        if 'aristotle_mdr_backwards' not in fetch_aristotle_settings().get('CONTENT_EXTENSIONS', []):
            bc_fields = self._meta.model.backwards_compatible_fields
            for fname in bc_fields:
                if fname in self.fields:
                    del self.fields[fname]

        for f in self.fields:
            if f == "workgroup":
                self.fields[f].widget = widgets.WorkgroupAutocompleteSelect()
                self.fields[f].widget.choices = self.fields[f].choices
                if not self.user.is_superuser:
                    self.fields['workgroup'].queryset = self.user.profile.editable_workgroups
            elif hasattr(self.fields[f], 'queryset') and type(self.fields[f].queryset) == ConceptQuerySet:
                if hasattr(self.fields[f].queryset, 'visible'):
                    if f in [m2m.name for m2m in self._meta.model._meta.many_to_many]:
                        field_widget = widgets.ConceptAutocompleteSelectMultiple
                    else:
                        field_widget = widgets.ConceptAutocompleteSelect
                    self.fields[f].queryset = self.fields[f].queryset.all().visible(self.user)
                    self.fields[f].widget = field_widget(model=self.fields[f].queryset.model)
                    self.fields[f].widget.choices = self.fields[f].choices
            elif hasattr(self.fields[f], 'queryset') and type(self.fields[f].queryset) == FrameworkDimensionQuerySet:
                if f in [m2m.name for m2m in self._meta.model._meta.many_to_many]:
                    field_widget = widgets.FrameworkDimensionAutocompleteSelectMultiple
                    self.fields[f].widget = field_widget(model=self.fields[f].queryset.model)
                    self.fields[f].queryset = self.fields[f].queryset.all()
            elif type(self.fields[f]) == forms.fields.DateField:
                self.fields[f].widget = BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"})
            elif type(self.fields[f]) == forms.fields.DateTimeField:
                self.fields[f].widget = BootstrapDateTimePicker(options={"format": "YYYY-MM-DD"})

        # Name suggest button
        aristotle_settings = fetch_aristotle_settings()
        self.fields['name'].widget = NameSuggestInput(
            name_suggest_fields=self._meta.model.name_suggest_fields,
            separator=aristotle_settings['SEPARATORS'].get(self._meta.model.__name__, '-')
        )

    def concept_fields(self):
        # version/workgroup are displayed with name/definition
        # This is where References, Origin URI, Origin and Comments are populated

        field_names = [field.name for field in MDR.baseAristotleObject._meta.fields] + ['version', 'workgroup']

        concept_field_names = [
            field.name for field in MDR.concept._meta.fields
            if field.name not in field_names
        ]
        for name in self.fields:
            if name in concept_field_names and name != 'make_new_item':
                yield self[name]

    def object_specific_fields(self):
        # returns every field that isn't in a concept
        obj_field_names = [
            field.name for field in self._meta.model._meta.get_fields()
            if field not in MDR.concept._meta.fields
        ]
        fields = []
        for name in self.fields:
            if name in obj_field_names:
                fields.append(self[name])
        return fields


class Concept_1_Search(UserAwareForm):
    template = "aristotle_mdr/create/concept_wizard_1_search.html"
    # Object class fields
    name = forms.CharField(max_length=256, required=False)
    version = forms.CharField(max_length=256, required=False)
    definition = forms.CharField(widget=forms.Textarea, required=False)

    def save(self, *args, **kwargs):
        pass


class Concept_2_Results(CustomValueFormMixin, ConceptForm):
    make_new_item = forms.BooleanField(
        initial=False,
        label=_("I've reviewed these items, and none of them meet my needs. Make me a new one."),
        error_messages={'required': 'You must select this to acknowledge you have reviewed the above items.'}
    )

    def __init__(self, *args, **kwargs):
        self.check_similar = kwargs.pop('check_similar', True)
        super().__init__(*args, **kwargs)
        self.fields['workgroup'].queryset = self.user.profile.editable_workgroups
        self.fields['workgroup'].initial = self.user.profile.activeWorkgroup
        if not self.check_similar:
            self.fields.pop('make_new_item')


def subclassed_modelform(set_model):
    class MyForm(ConceptForm):
        class Meta(ConceptForm.Meta):
            model = set_model
            fields = '__all__'

    return MyForm


def subclassed_mixin_modelform(set_model, extra_mixins=[]):
    meta_attrs = {'model': set_model}
    if set_model.edit_page_excludes:
        meta_attrs['exclude'] = set(list(UserAwareModelForm._meta.exclude) + list(set_model.edit_page_excludes))
    else:
        meta_attrs['exclude'] = UserAwareModelForm._meta.exclude  # '__all__'

    meta_class = type('Meta', (ConceptForm.Meta,), meta_attrs)

    form_class_bases = extra_mixins + [ConceptForm]
    form_class_attrs = {'Meta': meta_class,
                        'change_comments': forms.CharField(widget=forms.Textarea, required=False)}

    form_class = type('MyForm', tuple(form_class_bases), form_class_attrs)

    return form_class


def subclassed_edit_modelform(set_model, extra_mixins=[]):
    extra_mixins = [CheckIfModifiedMixin] + extra_mixins
    return subclassed_mixin_modelform(set_model, extra_mixins=extra_mixins)


def subclassed_clone_modelform(set_model, extra_mixins=[]):
    return subclassed_mixin_modelform(set_model, extra_mixins=extra_mixins)


def subclassed_wizard_2_Results(set_model):
    class MyForm(Concept_2_Results):
        class Meta(Concept_2_Results.Meta):
            model = set_model
            extra = []
            if set_model.edit_page_excludes:
                exclude = set(list(UserAwareModelForm._meta.exclude) + list(set_model.edit_page_excludes))
            else:
                fields = '__all__'
    return MyForm


class DEC_OCP_Search(UserAwareForm):
    template = "aristotle_mdr/create/dec_1_initial_search.html"
    # Object class fields
    oc_name = forms.CharField(max_length=256)
    oc_desc = forms.CharField(widget=forms.Textarea, required=False)
    # Property fields
    pr_name = forms.CharField(max_length=256)
    pr_desc = forms.CharField(widget=forms.Textarea, required=False)

    def save(self, *args, **kwargs):
        pass


class DEC_OCP_Results(UserAwareForm):
    def __init__(self, oc_similar=None, pr_similar=None, oc_duplicate=None, pr_duplicate=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if oc_similar:
            oc_options = [
                (oc.object.id, oc)
                for oc in oc_similar
                if oc.object
            ]
            oc_options.append(("X", "None of the above meet my needs"))
            self.fields['oc_options'] = forms.ChoiceField(
                label="Similar Object Classes",
                choices=oc_options,
                widget=forms.RadioSelect()
            )
        if pr_similar:
            pr_options = [
                (pr.object.id, pr)
                for pr in pr_similar
                if pr.object
            ]
            pr_options.append(("X", "None of the above meet my needs"))
            self.fields['pr_options'] = forms.ChoiceField(
                label="Similar Properties",
                choices=tuple(pr_options),
                widget=forms.RadioSelect()
            )

    def clean_oc_options(self):
        if self.cleaned_data['oc_options'] == "X":
            # The user chose to make their own item, so return No item.
            return None
        try:
            oc = MDR.ObjectClass.objects.get(pk=self.cleaned_data['oc_options'])
            return oc
        except ObjectDoesNotExist:
            return None

    def clean_pr_options(self):
        if self.cleaned_data['pr_options'] == "X":
            # The user chose to make their own item, so return No item.
            return None
        try:
            return MDR.Property.objects.get(pk=self.cleaned_data['pr_options'])
        except ObjectDoesNotExist:
            return None

    def save(self, *args, **kwargs):
        pass


class DEC_Find_DEC_Results(Concept_2_Results):
    class Meta(Concept_2_Results.Meta):
        model = MDR.DataElementConcept


class DEC_Complete(UserAwareForm):
    make_items = forms.BooleanField(
        initial=False,
        label=_("I've reviewed these items, and wish to create them."),
        error_messages={'required': 'You must select this to ackowledge you have reviewed the above items.'}
    )

    def save(self, *args, **kwargs):
        pass


# Data Element - Object Class / Property / Value Domain search form
class DE_OCPVD_Search(UserAwareForm):
    template = "aristotle_mdr/create/de_1_initial_search.html"
    # Object Class fields
    oc_name = forms.CharField(max_length=256)
    oc_desc = forms.CharField(widget=forms.Textarea, required=False)
    # Property fields
    pr_name = forms.CharField(max_length=256)
    pr_desc = forms.CharField(widget=forms.Textarea, required=False)
    # Value Domain fields
    vd_name = forms.CharField(max_length=256)
    vd_desc = forms.CharField(widget=forms.Textarea, required=False)

    def save(self, *args, **kwargs):
        pass


class DE_OCPVD_Results(DEC_OCP_Results):
    def __init__(self, vd_similar=None, vd_duplicate=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if vd_similar:
            vd_options = [
                (vd.object.id, vd)
                for vd in vd_similar
                if vd.object
            ]
            vd_options.append(("X", "None of the above meet my needs"))
            self.fields['vd_options'] = forms.ChoiceField(
                label="Similar Value Domains",
                choices=tuple(vd_options),
                widget=forms.RadioSelect()
            )

    def clean_vd_options(self):
        if self.cleaned_data['vd_options'] == "X":
            # The user chose to make their own item, so return No item.
            return None
        try:
            return MDR.ValueDomain.objects.get(pk=self.cleaned_data['vd_options'])
        except ObjectDoesNotExist:
            return None

    def save(self, *args, **kwargs):
        pass


class DE_Find_DEC_Results(UserAwareForm):
    def __init__(self, *args, **kwargs):
        dec_similar = kwargs.pop('dec_similar')
        super().__init__(*args, **kwargs)
        if dec_similar:
            dec_options = [(dec.id, dec) for dec in dec_similar]
            dec_options.append(("X", "None of the above meet my needs"))
            self.fields['dec_options'] = forms.ChoiceField(
                label="Similar Data Element Concepts",
                choices=tuple(dec_options),
                widget=forms.RadioSelect()
            )

    def clean_dec_options(self):
        if self.cleaned_data['dec_options'] == "X":
            # The user chose to make their own item, so return No item.
            return None
        try:
            dec = MDR.DataElementConcept.objects.get(pk=self.cleaned_data['dec_options'])
            return dec
        except ObjectDoesNotExist:
            return None

    def save(self, *args, **kwargs):
        pass


class DE_Find_DE_Results_from_components(UserAwareForm):
    make_new_item = forms.BooleanField(
        initial=False,
        label=_("I've reviewed these items, and none of them meet my needs. Make me a new one."),
        error_messages={'required': 'You must select this to ackowledge you have reviewed the above items.'}
    )

    def save(self, *args, **kwargs):
        pass


class DE_Find_DE_Results(Concept_2_Results):
    class Meta(Concept_2_Results.Meta):
        model = MDR.DataElement


class DE_Complete(UserAwareForm):
    make_items = forms.BooleanField(
        initial=False,
        label=_("I've reviewed these items, and wish to create them."),
        error_messages={'required': 'You must select this to acknowledge you have reviewed the above items.'}
    )

    def save(self, *args, **kwargs):
        pass


def record_relation_inlineformset_factory():
    """Create an inline formset factory for organization record"""
    base_formset = inlineformset_factory(
        MDR._concept, MDR.RecordRelation,
        can_delete=True,
        fields=('concept', 'type', 'organization_record'),
        widgets={
            'type': forms.widgets.Select(attrs={'class': 'form-control'}),
            'organization_record': forms.widgets.Select(attrs={'class': 'form-control'})
        },
        extra=1,
    )
    return base_formset


def reference_link_inlineformset_factory():
    """Create an inline formset factory for organization record"""
    from aristotle_cloud.contrib.steward_extras.models import MetadataReferenceLink
    base_formset = inlineformset_factory(
        MDR._concept, MetadataReferenceLink,
        can_delete=True,
        fields=('metadata', 'reference', 'description'),
        widgets={
            'reference': forms.widgets.Select(attrs={'class': 'form-control'}),
            # 'organization_record': forms.widgets.Select(attrs={'class': 'form-control'})
        },
        extra=1,
    )
    return base_formset
