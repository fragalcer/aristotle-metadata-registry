from typing import Dict, List
from braces.views import LoginRequiredMixin, PermissionRequiredMixin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q, Model
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.forms.models import model_to_dict
from django.http import (
    Http404,
    JsonResponse,
)
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property, SimpleLazyObject
from django.utils.translation import ugettext_lazy as _
from django.views.generic import (
    DetailView, FormView, ListView, TemplateView
)
from django.views.generic.detail import BaseDetailView, SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from aristotle_mdr import models as MDR
from aristotle_mdr.perms import user_can_view
from aristotle_mdr.models import _concept
from aristotle_mdr.contrib.favourites.models import Favourite, Tag
from aristotle_mdr.structs import Breadcrumb, ReversibleBreadcrumb

import datetime
import json

import logging

logger = logging.getLogger(__name__)

paginate_sort_opts = {
    "mod_asc": ["modified"],
    "mod_desc": ["-modified"],
    "cre_asc": ["created"],
    "cre_desc": ["-created"],
    "name_asc": [Lower("name").asc()],
    "name_desc": [Lower("name").desc()],
}


@login_required
def paginated_list(request, items, template, extra_context={}):
    if hasattr(items, 'select_subclasses'):
        items = items.select_subclasses()
    sort_by = request.GET.get('sort', "mod_desc")
    if sort_by not in paginate_sort_opts.keys():
        sort_by = "mod_desc"

    paginator = Paginator(
        items.order_by(*paginate_sort_opts.get(sort_by)),
        request.GET.get('pp', 20)  # per page
    )

    page = request.GET.get('page')
    try:
        paged_items = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        paged_items = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        paged_items = paginator.page(paginator.num_pages)
    context = {
        'object_list': items,
        'sort': sort_by,
        'page': paged_items,
    }
    context.update(extra_context)
    return render(request, template, context)


@login_required
def paginated_reversion_list(request, items, template, extra_context={}):
    paginator = Paginator(
        items,
        request.GET.get('pp', 20)  # per page
    )

    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        items = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        items = paginator.page(paginator.num_pages)
    context = {
        'page': items,
    }
    context.update(extra_context)
    return render(request, template, context)


paginate_workgroup_sort_opts = {
    "users": ("user_count", lambda qs: qs.annotate(user_count=Count('viewers'))),
    "items": ("item_count", lambda qs: qs.annotate(item_count=Count('items'))),
    "name": "name",
}


@login_required
def paginated_workgroup_list(request, workgroups, template, extra_context={}):
    sort_by = request.GET.get('sort', "name_desc")
    try:
        sorter, direction = sort_by.split('_')
        if sorter not in paginate_workgroup_sort_opts.keys():
            sorter = "name"
            sort_by = "name_desc"
        direction = {'asc': '', 'desc': '-'}.get(direction, '')
    except:
        sorter, direction = 'name', ''

    opts = paginate_workgroup_sort_opts.get(sorter)
    qs = workgroups

    try:
        sort_field, extra = opts
        qs = extra(qs)
    except:
        sort_field = opts

    qs = qs.order_by(direction + sort_field)
    paginator = Paginator(
        qs,
        request.GET.get('pp', 20)  # per page
    )

    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        items = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        items = paginator.page(paginator.num_pages)
    context = {
        'sort': sort_by,
        'page': items,
    }
    context.update(extra_context)
    return render(request, template, context)


paginate_registration_authority_sort_opts = {
    "name": "name",
    "users": ("user_count", lambda qs: qs.annotate(user_count=Count('registrars') + Count('managers'))),
}


def paginated_registration_authority_list(request, ras, template, extra_context={}):
    sort_by = request.GET.get('sort', "name_asc")
    try:
        sorter, direction = sort_by.split('_')
        if sorter not in paginate_registration_authority_sort_opts.keys():
            sorter = "name"
            sort_by = "name_desc"
        direction = {'asc': '', 'desc': '-'}.get(direction, '')
    except:
        sorter, direction = 'name', ''

    opts = paginate_registration_authority_sort_opts.get(sorter)
    qs = ras

    try:
        sort_field, extra = opts
        qs = extra(qs)
    except:
        sort_field = opts

    qs = qs.order_by(direction + sort_field)
    qs = qs.annotate(user_count=Count('registrars', distinct=True) + Count('managers', distinct=True))
    paginator = Paginator(
        qs,
        request.GET.get('pp', 20)  # per page
    )

    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        items = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        items = paginator.page(paginator.num_pages)
    context = {
        'sort': sort_by,
        'page': items,
    }

    context.update(extra_context)
    return render(request, template, context)


def workgroup_item_statuses(workgroup):
    from aristotle_mdr.models import STATES

    raw_counts = workgroup.items.filter(
        Q(statuses__until_date__gte=timezone.now()) |
        Q(statuses__until_date__isnull=True)
    ).values_list('statuses__state').annotate(num=Count('id', distinct=True))

    counts = []
    for state, count in raw_counts:
        if state is None:
            state = _("Not registered")
        else:
            state = STATES[state]
        counts.append((state, count))
    return counts


def generate_visibility_matrix(user):
    matrix = {}

    from aristotle_mdr.models import STATES

    for ra in user.profile.registrarAuthorities:
        ra_matrix = {'name': ra.name, 'states': {}}
        for s, name in STATES:
            if s >= ra.public_state:
                ra_matrix['states'][s] = "public"
            elif s >= ra.locked_state:
                ra_matrix['states'][s] = "locked"
            else:
                ra_matrix['states'][s] = "hidden"
        matrix[ra.id] = ra_matrix
    return matrix


def get_query_safe_context(context):
    """
    Returns context as static data forcing no further queries to be executed
    Note this will evaluate all querysets in the context
    """

    update = {}
    for key, value in context.items():

        if isinstance(value, Model):
            update[key] = model_to_dict(value)

        if isinstance(value, QuerySet):
            update[key] = value.values()

    context.update(update)
    return context


def get_status_queryset():
    """
    Get a queryset for all valid statuses and their ra's
    """

    return (
        MDR.Status.objects.valid().order_by("registrationAuthority", "-registrationDate", "-created")
                          .select_related('registrationAuthority')
    )


class SortedListView(ListView):
    """
    Can be used to replace current paginated function views,
    while retaining the template

    allowed_sorts can be a dict mapping names to sorts or just a list of sorts
    """

    allowed_sorts: Dict[str, str] = {}
    default_sort = ''

    def dispatch(self, request, *args, **kwargs):
        self.text_filter = request.GET.get('filter', "")
        self.sort = request.GET.get('sort', "")
        return super().dispatch(request, *args, **kwargs)

    def sort_queryset(self, queryset):
        # To be used in get_queryset
        sort = ''
        asc = True
        if self.sort:
            if '_' in self.sort:
                parts = self.sort.split('_')
                sort = parts[0]
                if parts[1] == 'desc':
                    asc = False
            else:
                sort = self.sort

            if sort in self.allowed_sorts:

                if type(self.allowed_sorts) == dict:
                    sort = self.allowed_sorts[sort]

                if not asc:
                    sort = '-' + sort

                return queryset.order_by(sort)

        if not self.default_sort:
            return queryset
        else:
            return queryset.order_by(self.default_sort)

    def get_context_data(self):
        context = super().get_context_data()
        context.update({
            'filter': self.text_filter,
            'page': context['page_obj'],
            'sort': self.sort
        })
        return context


class AnnotatedPaginator(Paginator):
    def __init__(self, *args, **kwargs):
        self.annotations = kwargs.pop('annotations', {})
        super().__init__(*args, **kwargs)

    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        number = self.validate_number(number)
        bottom = (number - 1) * self.per_page
        top = bottom + self.per_page
        if top + self.orphans >= self.count:
            top = self.count
        annotated_list = self.object_list
        if self.annotations:
            annotated_list = annotated_list.annotate(**self.annotations)
        return self._get_page(annotated_list[bottom:top], number, self)


class GenericListWorkgroup(LoginRequiredMixin, SortedListView):
    model = MDR.Workgroup
    redirect_unauthenticated_users = True

    paginate_by = 20
    paginator_class = AnnotatedPaginator

    allowed_sorts = {
        'items': 'num_items',
        'name': 'name',
    }

    default_sort = 'name'

    def get_initial_queryset(self):
        raise NotImplementedError

    def get_paginator(self, *args, **kwargs):
        annotations = {
            'num_items': Count('items')  # , distinct=True),
            # 'num_members': Count('members') # , distinct=True)
        }
        return self.paginator_class(*args, **kwargs, annotations=annotations)

    def get_queryset(self):
        workgroups = self.get_initial_queryset()
        if self.text_filter:
            workgroups = workgroups.filter(
                Q(name__icontains=self.text_filter) | Q(definition__icontains=self.text_filter))
        workgroups = self.sort_queryset(workgroups)

        return workgroups


class ObjectLevelPermissionRequiredMixin(PermissionRequiredMixin):
    object_level_permissions = True


class GroupMemberMixin(object):
    user_pk_kwarg = "user_pk"

    @cached_property
    def user_to_change(self):
        from aristotle_mdr.contrib.groups.base import AbstractGroup

        user = get_object_or_404(get_user_model(), pk=self.kwargs.get(self.user_pk_kwarg))
        obj = self.get_object()
        if issubclass(obj.__class__, AbstractGroup):
            if not self.get_object().has_member(user):
                raise Http404
        else:
            if user not in self.get_object().members.all():
                raise Http404
        return user

    def get_context_data(self, **kwargs):
        """
        Insert the single object into the context dict.
        """
        kwargs = super().get_context_data(**kwargs)
        kwargs.update({'user_to_change': self.user_to_change})
        return kwargs


class RoleChangeView(GroupMemberMixin, LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, BaseDetailView,
                     FormView):
    raise_exception = True
    redirect_unauthenticated_users = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'user': self.request.user})
        initial = {'roles': self.get_object().list_roles_for_user(self.user_to_change)}

        kwargs.update({'initial': initial})
        return kwargs

    def form_valid(self, form):
        for role in self.model.roles:
            if role in form.cleaned_data['roles']:
                self.get_object().giveRoleToUser(role, self.user_to_change)
            else:
                self.get_object().removeRoleFromUser(role, self.user_to_change)

        return self.get_success_url()


class SingleRoleChangeView(GroupMemberMixin, LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, BaseDetailView,
                           FormView):
    raise_exception = True
    redirect_unauthenticated_users = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'user': self.request.user})
        initial = {'role': None}
        current_role = self.get_object().list_roles_for_user(self.user_to_change)
        if current_role:
            initial['role'] = current_role[0]

        kwargs.update({'initial': initial})
        return kwargs

    def form_valid(self, form):
        self.get_object().giveRoleToUser(form.cleaned_data['role'], self.user_to_change)
        return self.get_success_url()


class MemberRemoveFromGroupView(GroupMemberMixin, LoginRequiredMixin, ObjectLevelPermissionRequiredMixin, DetailView):
    raise_exception = True
    redirect_unauthenticated_users = True

    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        self.get_object().removeUser(self.user_to_change)
        return self.get_success_url()


class AlertFieldsMixin:
    """Provide a list of fields where help text should be rendered as an alert"""

    alert_fields: list = []

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({'alert_fields': self.alert_fields})
        return context


class UserFormViewMixin:
    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs['user'] = self.request.user
        return kwargs


class AjaxFormMixin:
    """
    Mixin to be used with form view for ajax functionality,
    falls back to normal functionality when recieving a non ajax request

    Requirements:
    - ajaxforms.js must be included on the page
    - divs containing form fields must have the class field-container

    Optional:
    - div with class ajax-success-container to control where success message
    appears
    """

    ajax_success_message = ''

    def form_invalid(self, form):

        if self.request.is_ajax():
            # Return errors as json
            data = {
                'success': False,
                'errors': form.errors
            }
            return JsonResponse(data)
        else:
            return super().form_invalid(form)

    def form_valid(self, form):
        # Need to call super here for modelFormMixin compatibility
        response = super().form_valid(form)

        if self.request.is_ajax():
            data = {'success': True}
            # If success message set
            if self.ajax_success_message:
                data['message'] = self.ajax_success_message
                return JsonResponse(data)
            else:
                # Return success url
                data['redirect'] = self.get_success_url()
                return JsonResponse(data)
        else:
            return response


class CachePerItemUserMixin:
    cache_item_kwarg = 'iid'
    cache_view_name = ''
    cache_ttl = 300

    def get(self, request, *args, **kwargs):
        if not settings.CACHE_ITEM_PAGE:
            return super().get(request, *args, **kwargs)

        if request.user.is_anonymous:
            user = 'anonymous'
        else:
            user = request.user.id

        iid = kwargs[self.cache_item_kwarg]

        CACHE_KEY = 'view_cache_%s_%s_%s' % (self.cache_view_name, user, iid)

        can_use_cache = True

        if 'nocache' in request.GET.keys():
            can_use_cache = False

        from aristotle_mdr.models import _concept

        # If the item was modified within ttl, don't use cache
        recently = timezone.now() - datetime.timedelta(seconds=self.cache_ttl)
        if _concept.objects.filter(id=iid, modified__gte=recently).exists():
            can_use_cache = False

        if can_use_cache:
            response = cache.get(CACHE_KEY, None)
            if response is not None:
                return response

        response = super().get(request, *args, **kwargs)
        response.render()

        if can_use_cache:
            cache.set(CACHE_KEY, response, self.cache_ttl)

        return response


class TagsMixin:

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data()

        if self.request.user.is_authenticated:
            item_tags = Favourite.objects.filter(
                tag__profile=self.request.user.profile,
                tag__primary=False,
                item=self.item
            ).order_by('created').values('tag__id', 'tag__name')

            user_tags = Tag.objects.filter(
                profile=self.request.user.profile,
                primary=False
            ).values('id', 'name')

            item_tags = list(item_tags)
            user_tags = list(user_tags)

            context['item_tags'] = json.dumps(item_tags)
            context['user_tags'] = json.dumps(user_tags)

        else:
            context['item_tags'] = []
            context['user_tags'] = []

        return context


class SimpleItemGet:
    item_id_arg = 'iid'

    def get_item(self, user):
        item_id = self.kwargs.get(self.item_id_arg, None)
        if item_id is None:
            raise Http404

        try:
            item = _concept.objects.get(id=item_id)
        except _concept.DoesNotExist:
            raise Http404

        if not user_can_view(user, item):
            raise PermissionDenied

        return item

    def dispatch(self, request, *args, **kwargs):
        item = self.get_item(request.user)

        self.item = item
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['item'] = self.item.item
        return context


class FormsetView(TemplateView):
    """
    Generic View for handling formsets
    Similar in structure to django's FormView
    """

    save_methods: List[str] = ['POST']

    def get_formset_class(self):
        raise NotImplementedError

    def get_formset_initial(self):
        return []

    def get_formset_kwargs(self):
        kwargs = {
            'initial': self.get_formset_initial()
        }
        if self.request.method in self.save_methods:
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES
            })
        return kwargs

    def get_formset(self):
        formset_class = self.get_formset_class()
        return formset_class(**self.get_formset_kwargs())

    def post(self, request, *args, **kwargs):
        formset = self.get_formset()
        if formset.is_valid():
            return self.formset_valid(formset)
        else:
            return self.formset_invalid(formset)

    def formset_valid(self, formset):
        raise NotImplementedError

    def formset_invalid(self, formset):
        return self.render_to_response(self.get_context_data(formset=formset))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if 'formset' not in context:
            context['formset'] = self.get_formset()
        return context


# Thanks: https://stackoverflow.com/questions/17192737/django-class-based-view-for-both-create-and-update
class CreateUpdateView(SingleObjectTemplateResponseMixin, ModelFormMixin, ProcessFormView):
    def get_object(self, queryset=None):
        try:
            return super(CreateUpdateView, self).get_object(queryset)
        except AttributeError:
            return None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(CreateUpdateView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(CreateUpdateView, self).post(request, *args, **kwargs)


def get_lazy_viewable_ids(user):
    return SimpleLazyObject(
        lambda: list(MDR._concept.objects.visible(user).values_list('id', flat=True))
    )


def add_item_url(item, active=False) -> Breadcrumb:
    """Helper function to add item breadcrumbs """
    if active:
        return Breadcrumb(item.name, active=True)
    return ReversibleBreadcrumb(item.name, 'aristotle:item', url_args=[item.id])


def share_link_possible(submitter) -> bool:
    """Returns true if a share link can be created to another user's sandbox"""
    if not submitter:
        return False
    else:
        if not hasattr(submitter.profile, 'share'):
            return False
    return True


def get_item_breadcrumbs(item: _concept, user, last_active=True) -> List[Breadcrumb]:
    """ Return a list of breadcrumbs for a metadata item
        through a process of introspection to determine what kind of breadcrumbs to display

        last_active: Make the item link an active link if deeper pages exist"""
    if item.is_sandboxed:
        # It's in a sandbox
        if item.submitter == user:
            # It's in our own sandbox
            return [ReversibleBreadcrumb('My Sandbox', 'aristotle_mdr:userSandbox'),
                    add_item_url(item, active=last_active)]
        else:
            # It's in another user's sandbox
            no_link_possible = False
            if not item.submitter:
                return []

            if share_link_possible(item.submitter):
                # You are viewing the item without a share being created, this is something only a superuser could do
                other_users_name = item.submitter.display_name
                share = item.submitter.profile.share
                return [
                    ReversibleBreadcrumb(f"{other_users_name}'s Sandbox",
                                         'aristotle:sharedSandbox',
                                         url_args=[share.uuid]),
                    add_item_url(item, active=last_active)
                ]

            else:
                return [
                    Breadcrumb(f"Sandboxed Item"),
                    add_item_url(item, active=last_active)
                ]
    elif item.stewardship_organisation:
        # Item has a stewardship organisation
        content_type = ContentType.objects.get_for_model(type(item))
        return [
            Breadcrumb(item.stewardship_organisation.name,
                       item.stewardship_organisation.get_absolute_url()),
            ReversibleBreadcrumb('Metadata',
                                 'aristotle_mdr:stewards:group:browse',
                                 url_args=[item.stewardship_organisation.slug]),

            ReversibleBreadcrumb(f'{item.item_type_name}',
                                 'aristotle_mdr:stewards:group:browse_app_metadata',
                                 url_args=[item.stewardship_organisation.slug,
                                           content_type.app_label,
                                           content_type.model]),

            add_item_url(item, active=last_active)
        ]
    return []
