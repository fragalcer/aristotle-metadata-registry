from typing import List, Sequence
from django.db.models import Q
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.admin.filters import RelatedFieldListFilter
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

import aristotle_mdr.models as MDR
import aristotle_mdr.forms as MDRForms
from aristotle_mdr import perms
from reversion_compare.admin import CompareVersionAdmin

from aristotle_mdr.search_indexes import ConceptIndex
from haystack import indexes

import reversion
from improved_user.forms import UserChangeForm, UserCreationForm

from aristotle_mdr.register import register_concept
from aristotle_mdr.utils import fetch_aristotle_settings

reversion.revisions.register(MDR.Status)
reversion.revisions.register(MDR.RecordRelation)
reversion.revisions.register(
    MDR._concept,
    follow=[
        'statuses', 'slots', 'identifiers'
    ],
    exclude=[
        'is_public', 'is_locked',
        'user_view_history',
        'superseded_by_items', 'superseded_items',
        'superseded_by_items_relation_set',
        'superseded_items_relation_set',
        'modified',
        'submitter',
        'issues'
    ]
)
reversion.revisions.register(MDR.Workgroup)
reversion.revisions.register(MDR.SupersedeRelationship)

User = get_user_model()


class StatusInline(admin.TabularInline):
    """
    Inline editor for registration status records
    """

    model = MDR.Status
    form = MDRForms.admin.StatusInlineForm
    extra = 0

    """
    The default queryset will return all objects of a given type.
    This limits the returned Status Records to only those where
    they are in a Registration Authority in which the current user
    has permission to change the status of objects.
    """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(registrationAuthority__in=request.user.registrar_in.all())
        return qs

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return perms.user_can_add_status(request.user, obj)
        return super().has_change_permission(request, obj=None)

    def has_add_permission(self, request):
        if perms.user_is_registrar(request.user):
            return True
        return super().has_add_permission(request)


class WorkgroupFilter(RelatedFieldListFilter):
    def __init__(self, field, request, *args, **kwargs):
        super().__init__(field, request, *args, **kwargs)
        if not request.user.is_superuser:
            self.lookup_choices = [(w.id, w) for w in request.user.profile.workgroups.all()]


class WorkgroupAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'definition']}),
        # ('Members', {'fields': ['managers', 'stewards', 'submitters', 'viewers']}),
    ]
    # filter_horizontal = ['managers', 'stewards', 'submitters', 'viewers']
    list_display = ('name', 'definition', 'archived')
    list_filter = ('archived',)
    search_fields = ('name', 'definition')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        else:
            return request.user.profile.workgroups.all()

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if obj is None:
            if request.GET.get('t', None) == "registrygroup_ptr":
                return True
            else:
                return True in (
                    request.user.has_perm(
                        'aristotle_mdr.admin_in_{name}'.format(name=w.name)
                    ) for w in request.user.profile.workgroups.all()
                )
        elif perms.user_can_edit(request.user, obj):
            return True
        else:
            return super().has_change_permission(request, obj=None)


class ConceptAdmin(admin.ModelAdmin):

    form = MDRForms.admin.AdminConceptForm
    list_display = ['name', 'description_stub', 'created', 'modified', 'workgroup', 'is_public', 'is_locked']  # ,'status']
    list_filter = ['created', 'modified', ('workgroup', WorkgroupFilter)]  # , 'statuses']
    search_fields = ['name']
    inlines = [StatusInline]

    date_hierarchy = 'created'  # ,'modified']

    fieldsets = [
        (None, {'fields': ['name', 'definition', 'workgroup']}),
        ('Additional names', {
            'classes': ('grp-collapse grp-closed',),
            'fields': ['version']
        }),
        # ('Registry', {'fields': ['workgroup']}),
        ('Relationships', {
            'classes': ('grp-collapse grp-closed',),
            'fields': ['origin_URI'],
        }),
    ]
    name_suggest_fields: List[str] = []
    actions_on_top = True
    actions_on_bottom = False

    compare_exclude = ['favourites', 'user_view_history', 'issues', 'owned_links']

    def get_form(self, request, obj=None, **kwargs):
        # Thanks: http://stackoverflow.com/questions/6321916
        # Thanks: http://stackoverflow.com/questions/2683689
        conceptForm = super().get_form(request, obj, **kwargs)

        class ModelFormMetaClass(conceptForm):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                kwargs['name_suggest_fields'] = self.name_suggest_fields
                if self.name_suggest_fields:
                    SEPARATORS = fetch_aristotle_settings().get('SEPARATORS', {})
                    kwargs['separator'] = SEPARATORS[self.model.__name__]
                return conceptForm(*args, **kwargs)

        return ModelFormMetaClass

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        else:
            return perms.user_can_edit(request.user, obj)

    def has_add_permission(self, request):
        return perms.user_is_authenticated_and_active(request.user)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return perms.user_is_authenticated_and_active(request.user)
        else:
            return request.user.has_perm("aristotle_mdr.delete_concept_from_admin", obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            if not self.has_change_permission(request):
                queryset = queryset.none()
            else:
                queryset = queryset.editable(request.user).all()
        return queryset

    # On save or add, redirect to the live page.
    # Implementing this would be nice:
    #      http://www.szotten.com/david/custom-redirects-in-the-django-admin.html
    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj)
        if '_save' in request.POST and post_url_continue is None:
            response['location'] = reverse("aristotle:item", args=(obj.id,))
        return response

    def response_change(self, request, obj, post_url_continue=None):
        response = super().response_change(request, obj)
        if '_save' in request.POST and post_url_continue is None:
            response['location'] = reverse("aristotle:item", args=(obj.id,))
        return response

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.submitter = request.user
        obj.save()


# For ValueDomains
class CodeValueInline(admin.TabularInline):
    form = MDRForms.PermissibleValueForm
    # fields = ("value","meaning")
    sortable_field_name = "order"
    extra = 1


class PermissibleValueInline(CodeValueInline):
    model = MDR.PermissibleValue


class SupplementaryValueInline(CodeValueInline):
    model = MDR.SupplementaryValue


# For ConceptualDomains
class ValueMeaningInline(admin.TabularInline):
    model = MDR.ValueMeaning
    fields = ("order", "name", "definition", "start_date", "end_date")
    sortable_field_name = "order"
    extra = 1


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'definition', 'created', 'modified']
    list_filter = ['created', 'modified']

    actions = ['promote_to_ra']

    def promote_to_ra(self, request, queryset):
        from django.contrib import messages
        from django.contrib.admin import helpers
        from django.contrib.admin.utils import model_ngettext
        if request.POST.get('post'):
            n = queryset.count()
            if n:
                for org in queryset.all():
                    org.promote_to_registration_authority()
                self.message_user(request, _("Successfully promoted %(count)d %(items)s.") % {
                    "count": n, "items": model_ngettext(self.opts, n)
                }, messages.SUCCESS)
            # Return None to display the change list page again.
            return None

        context = dict(
            self.admin_site.each_context(request),
            title=_("Are you sure?"),
            queryset=queryset,
            action_checkbox_name=helpers.ACTION_CHECKBOX_NAME,
            media=self.media,
            opts=self.model._meta
        )

        request.current_app = self.admin_site.name

        # Display the confirmation page
        from django.template.response import TemplateResponse
        return TemplateResponse(request, ["admin/promote_org_to_ra.html"], context)

    promote_to_ra.short_description = "Promote to registration authority"  # type: ignore


class RegistrationAuthorityAdmin(admin.ModelAdmin):
    list_display = ['name', 'definition', 'created', 'modified']
    list_filter = ['created', 'modified']
    filter_horizontal = ['managers', 'registrars']

    fieldsets = [
        (None, {'fields': ['name', 'definition', 'active']}),
        ('Members', {'fields': ['managers', 'registrars']}),
        ('Visibility and control', {'fields': ['locked_state', 'public_state']}),
        ('Status descriptions',
            {'fields': ['notprogressed', 'incomplete', 'candidate', 'recorded', 'qualified', 'standard', 'preferred', 'superseded', 'retired']}),
    ]


admin.site.register(MDR.Organization, OrganizationAdmin)
admin.site.register(MDR.RegistrationAuthority, RegistrationAuthorityAdmin)
admin.site.register(MDR.Workgroup, WorkgroupAdmin)

admin.site.register(MDR.Measure)
# admin.site.register(MDR.)


# Define an inline admin descriptor for Employee model
# which acts a bit like a singleton
class AristotleProfileInline(admin.StackedInline):
    model = MDR.PossumProfile
    form = MDRForms.admin.AristotleProfileForm
    exclude = ('savedActiveWorkgroup', 'favourites', 'profilePictureWidth',
               'profilePictureHeight', 'notificationPermissions', 'profilePicture')
    can_delete = False
    verbose_name_plural = 'Membership details'


class UserAdmin(BaseUserAdmin):
    """Admin panel for Improved User, mimics Django's default"""
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'short_name')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'short_name', 'password1', 'password2'),
        }),
    )
    form = UserChangeForm
    add_form = UserCreationForm
    list_display: Sequence = ('email', 'full_name', 'short_name', 'is_staff')
    search_fields = ('email', 'full_name', 'short_name')
    ordering = ('email',)


# Define a new User admin
class AristotleUserAdmin(UserAdmin):

    def time_since_login(self, obj):
        from django.contrib.humanize.templatetags.humanize import naturaltime
        return naturaltime(obj.last_login)

    time_since_login.admin_order_field = 'last_login'  # type: ignore
    time_since_login.short_description = _('Last login')  # type: ignore

    inlines = [AristotleProfileInline]
    list_display = ['email', 'full_name', 'short_name', 'time_since_login', 'date_joined']

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        for f in formset.forms:
            f.save_memberships(user=form.instance)


# Re-register UserAdmin
if User in admin.site._registry:
    admin.site.unregister(User)
admin.site.register(User, AristotleUserAdmin)


register_concept(MDR.ObjectClass)
register_concept(MDR.Property)
register_concept(
    MDR.ValueDomain,
    extra_fieldsets=[('Representation', {'fields': ['format', 'maximum_length', 'unit_of_measure', 'data_type', 'description']})],
    extra_inlines=[PermissibleValueInline, SupplementaryValueInline],
    reversion={
        'follow': ['permissiblevalue_set', 'supplementaryvalue_set'],
        'follow_classes': [MDR.PermissibleValue, MDR.SupplementaryValue]
    }
)


class aristotle_mdr_DataElementConceptSearchIndex(ConceptIndex, indexes.Indexable):
    data_element_concept = indexes.MultiValueField(model_attr="name", faceted=True, null=True)
    data_element_concept.title = 'Data element concept'
    object_class = indexes.MultiValueField(model_attr="objectClass__name", faceted=True, null=True)
    object_class.title = 'Object class'

    def get_model(self):
        return MDR.DataElementConcept


register_concept(
    MDR.DataElementConcept,
    name_suggest_fields=['objectClass', 'property'],
    extra_fieldsets=[('Components', {'fields': ['objectClass', 'property']})],
    custom_search_index=aristotle_mdr_DataElementConceptSearchIndex
)


class aristotle_mdr_DataElementSearchIndex(ConceptIndex, indexes.Indexable):
    data_element_concept = indexes.MultiValueField(model_attr="dataElementConcept__name", faceted=True, null=True)
    data_element_concept.title = 'Data element concept'
    object_class = indexes.MultiValueField(model_attr="dataElementConcept__objectClass__name", faceted=True, null=True)
    object_class.title = 'Object class'

    def get_model(self):
        return MDR.DataElement


register_concept(
    MDR.DataElement,
    name_suggest_fields=['dataElementConcept', 'valueDomain'],
    extra_fieldsets=[('Components', {'fields': ['dataElementConcept', 'valueDomain']})],
    custom_search_index=aristotle_mdr_DataElementSearchIndex
)


class aristotle_mdr_DataElementDerivationSearchIndex(ConceptIndex, indexes.Indexable):
    data_element_concept = indexes.MultiValueField(faceted=True, null=True)
    data_element_concept.title = 'Data element concept'
    object_class = indexes.MultiValueField(faceted=True, null=True)
    object_class.title = 'Object class'

    def get_model(self):
        return MDR.DataElementDerivation

    def prepare_data_element_concept(self, obj):
        return list(MDR.DataElementConcept.objects.filter(
            Q(dataelement__dedderivesthrough__data_element_derivation=obj) | Q(dataelement__dedinputsthrough__data_element_derivation=obj)
        ).values_list('name', flat=True))

    def prepare_object_class(self, obj):
        return list(MDR.ObjectClass.objects.filter(
            Q(dataelementconcept__dataelement__dedderivesthrough__data_element_derivation=obj) | Q(dataelementconcept__dataelement__dedinputsthrough__data_element_derivation=obj)
        ).values_list('name', flat=True))


class DedDerivesInline(admin.TabularInline):

    model = MDR.DedDerivesThrough
    verbose_name = "Derive"
    verbose_name_plural = "Derives"


class DedInputsInline(admin.TabularInline):

    model = MDR.DedInputsThrough
    verbose_name = "Input"
    verbose_name_plural = "Inputs"


register_concept(
    MDR.DataElementDerivation,
    extra_fieldsets=[('Derivation', {'fields': ['derivation_rule']})],
    extra_inlines=[DedDerivesInline, DedInputsInline],
    custom_search_index=aristotle_mdr_DataElementDerivationSearchIndex,
    reversion={
        'follow': ['dedinputsthrough_set', 'dedderivesthrough_set'],
        'follow_classes': [MDR.DedInputsThrough, MDR.DedDerivesThrough]
    }
)

register_concept(
    MDR.ConceptualDomain,
    extra_inlines=[ValueMeaningInline],
    reversion={
        'follow': ['valuemeaning_set'],
        'follow_classes': [MDR.ValueMeaning]
    }
)

register_concept(MDR.DataType)

register_concept(
    MDR.UnitOfMeasure,
    extra_fieldsets=[('Measures', {'fields': ['measure']})]
)
