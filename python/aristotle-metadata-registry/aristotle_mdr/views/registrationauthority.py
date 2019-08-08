import django_filters
import datetime
import string
import logging
from braces.views import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.forms import Select
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    CreateView,
    ListView,
    DetailView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin
from django.core.exceptions import PermissionDenied
from django.forms.models import modelform_factory
from django.http.request import QueryDict
from django_filters.views import FilterView
from dal.autocomplete import ModelSelect2Multiple
from aristotle_mdr import models as MDR
from aristotle_mdr.forms import actions
from aristotle_mdr.forms.registrationauthority import (
    CreateRegistrationAuthorityForm,
    EditRegistationAuthorityForm
)
from aristotle_mdr.views.utils import (
    paginated_registration_authority_list,
    ObjectLevelPermissionRequiredMixin,
    RoleChangeView,
    MemberRemoveFromGroupView,
    AlertFieldsMixin,
    UserFormViewMixin
)
from aristotle_mdr.widgets.bootstrap import BootstrapDateTimePicker
from aristotle_mdr import perms
from aristotle_mdr.utils import fetch_aristotle_downloaders
from aristotle_mdr.utils.utils import get_concept_type_choices
from aristotle_mdr.contrib.validators.views import ValidationRuleEditView
from aristotle_mdr.contrib.validators.models import RAValidationRules
from ckeditor.widgets import CKEditorWidget
from typing import Dict

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class MainPageMixin:
    """Mixin for views displaying on the main (public) ra page"""
    active_tab: str = 'home'

    def is_manager(self, ra):
        return perms.user_can_edit(self.request.user, ra)

    def get_tab_context(self):
        return {
            'active_tab': self.active_tab
        }


class RegistrationAuthorityView(MainPageMixin, DetailView):
    pk_url_kwarg = 'iid'
    queryset = MDR.RegistrationAuthority.objects.all()
    template_name = 'aristotle_mdr/organization/registration_authority/home.html'
    context_object_name = 'item'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update(self.get_tab_context())
        context['is_manager'] = self.is_manager(self.object)
        return context


def organization(request, iid, *args, **kwargs):
    if iid is None:
        return redirect(reverse("aristotle_mdr:all_organizations"))
    item = get_object_or_404(MDR.Organization, pk=iid).item

    return render(request, item.template, {'item': item.item})


def all_registration_authorities(request):
    # All visible ras
    ras = MDR.RegistrationAuthority.objects.filter(active__in=[0, 1]).order_by('name')
    return render(request, "aristotle_mdr/organization/all_registration_authorities.html",
                  {'registrationAuthorities': ras})


def all_organizations(request):
    orgs = MDR.Organization.objects.order_by('name')
    return render(request, "aristotle_mdr/organization/all_organizations.html", {'organization': orgs})


class CreateRegistrationAuthority(UserFormViewMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    template_name = "aristotle_mdr/user/registration_authority/add.html"
    # fields = ['name', 'definition', 'stewardship_organisation']
    permission_required = "aristotle_mdr.add_registration_authority"
    raise_exception = True
    redirect_unauthenticated_users = True
    model = MDR.RegistrationAuthority
    form_class = CreateRegistrationAuthorityForm

    def get_success_url(self):
        return reverse('aristotle:registrationAuthority', kwargs={'iid': self.object.id})


class AddUser(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, UpdateView):
    template_name = "aristotle_mdr/user/registration_authority/add_user.html"
    permission_required = "aristotle_mdr.change_registrationauthority_memberships"
    raise_exception = True
    redirect_unauthenticated_users = True
    form_class = actions.AddRegistrationUserForm

    model = MDR.RegistrationAuthority
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'user': self.request.user})

        # TODO: Not happy about this as its not an updateForm
        kwargs.pop('instance')
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(MDR.RegistrationAuthority, pk=self.kwargs.get('iid'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Insert the single object into the context dict.
        """
        kwargs = super().get_context_data(**kwargs)
        kwargs.update({'item': self.item})
        return kwargs

    def form_valid(self, form):
        user = form.cleaned_data['user']
        for role in form.cleaned_data['roles']:
            self.item.giveRoleToUser(role, user)

        return redirect(reverse('aristotle:registrationauthority_members', args=[self.item.id]))


class ListRegistrationAuthorityBase(ListView):
    model = MDR.RegistrationAuthority

    def get_queryset(self):
        return super().get_queryset().filter(active__in=[0, 1])

    def render_to_response(self, context, **response_kwargs):
        ras = self.get_queryset()

        text_filter = self.request.GET.get('filter', "")
        if text_filter:
            ras = ras.filter(Q(name__icontains=text_filter) | Q(definition__icontains=text_filter))
        context = self.get_context_data()
        context.update({'filter': text_filter})
        return paginated_registration_authority_list(self.request, ras, self.template_name, context)


class ListRegistrationAuthorityAll(LoginRequiredMixin, PermissionRequiredMixin, ListRegistrationAuthorityBase):
    template_name = "aristotle_mdr/user/registration_authority/list_all.html"
    permission_required = "aristotle_mdr.is_registry_administrator"
    raise_exception = True
    redirect_unauthenticated_users = True


class MembersRegistrationAuthority(LoginRequiredMixin, PermissionRequiredMixin, MainPageMixin, DetailView):
    model = MDR.RegistrationAuthority
    template_name = "aristotle_mdr/organization/registration_authority/members.html"
    permission_required = "aristotle_mdr.view_registrationauthority_details"
    raise_exception = True
    redirect_unauthenticated_users = True
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    active_tab = 'members'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_tab_context())
        context['is_manager'] = self.is_manager(self.object)
        context['ra_members'] = context['object'].members.all()
        context['managers'] = set(context['object'].managers.all().values_list("pk", flat=True))
        context['registrars'] = set(context['object'].registrars.all().values_list("pk", flat=True))
        return context


class EditRegistrationAuthority(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, AlertFieldsMixin, MainPageMixin,
                                UpdateView):
    model = MDR.RegistrationAuthority
    template_name = "aristotle_mdr/user/registration_authority/edit.html"
    permission_required = "aristotle_mdr.change_registrationauthority"
    raise_exception = True
    redirect_unauthenticated_users = True
    object_level_permissions = True

    fields = ('name', 'definition', 'active')
    widgets = {
        'definition': CKEditorWidget
    }

    alert_fields = [
        'active'
    ]

    pk_url_kwarg = 'iid'
    context_object_name = "item"

    active_tab = 'settings'

    def get_form_class(self):
        return modelform_factory(self.model, fields=self.fields, widgets=self.widgets)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update(self.get_tab_context())
        context['is_manager'] = self.is_manager(self.object)
        context['settings_tab'] = 'general'
        return context


class EditRegistrationAuthorityStates(LoginRequiredMixin,
                                      ObjectLevelPermissionRequiredMixin, MainPageMixin, UpdateView):
    model = MDR.RegistrationAuthority
    template_name = "aristotle_mdr/user/registration_authority/edit_states.html"
    permission_required = "aristotle_mdr.change_registrationauthority"
    raise_exception = True
    redirect_unauthenticated_users = True
    object_level_permissions = True

    form_class = EditRegistationAuthorityForm

    pk_url_kwarg = 'iid'
    context_object_name = "item"

    active_tab = 'settings'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update(self.get_tab_context())
        context['is_manager'] = self.is_manager(self.object)
        context['settings_tab'] = 'states'
        return context


class ChangeUserRoles(RoleChangeView):
    model = MDR.RegistrationAuthority
    template_name = "aristotle_mdr/user/registration_authority/change_role.html"
    permission_required = "aristotle_mdr.change_registrationauthority_memberships"
    form_class = actions.ChangeRegistrationUserRolesForm
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    def get_success_url(self):
        return redirect(reverse('aristotle:registrationauthority_members', args=[self.get_object().id]))


class RemoveUser(MemberRemoveFromGroupView):
    model = MDR.RegistrationAuthority
    template_name = "aristotle_mdr/user/registration_authority/remove_member.html"
    permission_required = "aristotle_mdr.change_registrationauthority_memberships"
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    def get_success_url(self):
        return redirect(reverse('aristotle:registrationauthority_members', args=[self.get_object().id]))


class RAValidationRuleEditView(SingleObjectMixin, MainPageMixin, ValidationRuleEditView):
    template_name = 'aristotle_mdr/organization/registration_authority/rules.html'
    model = MDR.RegistrationAuthority
    pk_url_kwarg = 'iid'
    context_object_name = 'item'

    active_tab = 'settings'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not perms.user_can_edit(self.request.user, obj):
            raise PermissionDenied

        return obj

    def get_rules(self):
        try:
            rules = RAValidationRules.objects.get(registration_authority=self.object)
        except RAValidationRules.DoesNotExist:
            return None
        return rules

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update(self.get_tab_context())
        context['is_manager'] = self.is_manager(self.object)
        context['settings_tab'] = 'validation'
        if context['rules'] is None:
            context['url'] = reverse('api_v4:create_ra_rules')
            context['method'] = 'post'
        else:
            context['url'] = reverse('api_v4:ra_rules', args=[context['rules'].id])
            context['method'] = 'put'
        return context


class ConceptFilter(django_filters.FilterSet):
    registration_date = django_filters.DateFilter(widget=BootstrapDateTimePicker,
                                                  method='noop')

    status = django_filters.ChoiceFilter(choices=MDR.STATES,
                                         method='noop',
                                         widget=Select(attrs={'class': 'form-control'}))

    letters = [(i, i) for i in string.ascii_uppercase + "&"]
    letter = django_filters.ChoiceFilter(choices=letters,
                                         method='noop',
                                         widget=Select(attrs={'class': 'form-control'}))

    class Meta:
        model = MDR._concept
        # Exclude unused fields, otherwise they appear in the template
        fields: list = []

    def noop(self, queryset, name, value):
        return queryset

    @property
    def qs(self):
        # We're doing all the filtering at once here in order to improve filtering performance
        from django.db.models.functions import Upper, Substr
        from django.db.models import Q, Subquery

        if not self.form.is_valid():
            return super().qs

        if not hasattr(self, '_qs'):
            qs = super().qs
            selected_date = self.form.cleaned_data['registration_date']
            selected_state = self.form.cleaned_data['status']
            selected_letter = self.form.cleaned_data['letter']

            selected_types = self.form.cleaned_data['concept_type']

            # If they haven't selected anything
            if selected_state == '':
                selected_state = None

            if not selected_types:
                selected_types = None

            # Return all the statuses that are valid at a particular date and then
            # filter on the concepts linked to a valid status.
            # Return only the statuses that are linked to the RA for the page that you are on
            status_is_valid = Q(
                statuses__in=Subquery(
                    MDR.Status.objects.filter(
                        state=selected_state,
                        registrationAuthority__id=self.registration_authority_id
                    ).valid_at_date(when=selected_date).values('pk')
                )
            )

            inner = MDR._concept.objects.filter(status_is_valid)
            qs = qs.filter(pk__in=Subquery(inner.values('pk'))).prefetch_related('statuses__registrationAuthority')

            # Filter on the selected concept types
            if selected_types is not None:
                qs = qs.filter(_type__in=selected_types)

            qs = qs.annotate(first_letter=Upper(Substr('name', 1, 1)))
            if selected_letter == "&":
                qs = qs.filter(~Q(first_letter__in=string.ascii_uppercase))
            elif selected_letter in string.ascii_uppercase:
                qs = qs.filter(name__istartswith=selected_letter)

            self._qs = qs.order_by(Upper('name'))

        return self._qs

    def __init__(self, *args, **kwargs):
        # Override the init method so we can pass the iid to the queryset
        self.registration_authority_id = kwargs.pop('registration_authority_id')

        # This is overridden because otherwise it runs on docs CI
        self.base_filters['concept_type'] = django_filters.MultipleChoiceFilter(
            choices=get_concept_type_choices(),
            method='noop',
            widget=ModelSelect2Multiple)

        super().__init__(*args, **kwargs)

        self.queryset = self.queryset.visible(self.request.user)


class DateFilterView(FilterView, MainPageMixin):
    active_tab = 'data_dictionary'

    filterset_class = ConceptFilter
    template_name = 'aristotle_mdr/organization/registration_authority/data_dictionary.html'
    paginate_by = 50

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context.update(self.get_tab_context())

        # Need to pass the ra context for use in building links in the template
        ra = MDR.RegistrationAuthority.objects.get(id=self.kwargs['iid'])
        context['item'] = ra
        context['is_manager'] = self.is_manager(ra)

        status = self.request.GET.get('status', MDR.STATES.standard)
        if status == '':
            # No status has been selected
            context['not_all_selected'] = True
            return context
        context['status'] = status

        selected_date = self.request.GET.get('registration_date', datetime.date.today())
        if selected_date == '':
            # No date has been selected
            context['not_all_selected'] = True
            return context

        context['date'] = selected_date

        concept_to_status: Dict = {}

        # Get the current statuses that are most up to date
        statuses = MDR.Status.objects.current(when=selected_date).filter(registrationAuthority=ra, state=status)

        for concept in context['object_list']:
            on_concept = Q(concept=concept)
            status = statuses.get(on_concept)
            concept_to_status[concept] = status

        context['concepts'] = concept_to_status
        context['downloaders'] = self.build_downloaders(context['object_list'])

        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs.update({'registration_authority_id': self.kwargs['iid']})

        if kwargs["data"] is None:
            # If there were no selections made in the form, set defaults
            kwargs["data"] = {"status": MDR.STATES.standard,
                              "registration_date": str(datetime.date.today())}

        if 'registration_date' not in kwargs['data']:
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['registration_date'] = datetime.date.today()

        if 'status' not in kwargs['data']:
            kwargs['data'] = kwargs['data'].copy()
            kwargs['data']['status'] = MDR.STATES.standard

        return kwargs

    def build_downloaders(self, queryset):
        downloaders = fetch_aristotle_downloaders()

        options: list = []

        ids = [concept.id for concept in queryset]

        for dl in downloaders:
            query = QueryDict(mutable=True)
            query.setlist('items', ids)

            url = '{url}?{qstring}'.format(
                url=reverse('aristotle:download_options', args=[dl.download_type]),
                qstring=query.urlencode()
            )

            options.append({'label': dl.label, 'url': url})

        return options
