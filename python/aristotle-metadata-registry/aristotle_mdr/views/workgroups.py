import logging

from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.groups.backends import GroupURLManager
from aristotle_mdr.perms import user_is_workgroup_manager
from aristotle_mdr.views.utils import (
    paginate_sort_opts,
    workgroup_item_statuses,
    ObjectLevelPermissionRequiredMixin,
    SingleRoleChangeView,
    MemberRemoveFromGroupView,
    GenericListWorkgroup,
    UserFormViewMixin
)
from aristotle_mdr.models import Workgroup

from braces.views import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.views.generic import (
    CreateView, DetailView, ListView, UpdateView, FormView
)

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class WorkgroupContextMixin(object):
    # workgroup = None
    raise_exception = True
    redirect_unauthenticated_users = True
    object_level_permissions = True
    model = MDR.Workgroup
    pk_url_kwarg = 'iid'
    slug_url_kwarg = 'name_slug'

    def get_context_data(self, **kwargs):
        # Get context from super-classes, because if may set value for workgroup
        context = super().get_context_data(**kwargs)
        context.update({
            'item': self.get_object(),
            'workgroup': self.get_object(),
            'user_is_admin': user_is_workgroup_manager(self.request.user, self.get_object()),
        })
        return context


class WorkgroupView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, DetailView):
    permission_required = "aristotle_mdr.view_workgroup"

    def get(self, request, *args, **kwargs):
        self.object = self.workgroup = self.get_object()
        # self.check_user_permission()
        slug = self.kwargs.get(self.slug_url_kwarg)
        if not slug or not slugify(self.object.name).startswith(slug):
            return redirect(self.object.get_absolute_url())
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        kwargs.update({
            'counts': workgroup_item_statuses(self.object),
            'recent': MDR._concept.objects.filter(
                workgroup=self.object).select_subclasses().order_by('-modified')[:5]
        })
        return super().get_context_data(**kwargs)

    def get_template_names(self):
        return self.object and [self.object.template] or []


class ItemsView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, ListView):
    template_name = "aristotle_mdr/workgroupItems.html"
    sort_by = None
    permission_required = "aristotle_mdr.view_workgroup"

    def get_object(self):
        return self.model.objects.get(pk=self.kwargs.get(self.pk_url_kwarg))

    def get_paginate_by(self, queryset):
        return self.request.GET.get('pp', 20)

    def get_context_data(self, **kwargs):
        kwargs.update({
            'sort': self.sort_by,
        })
        context = super().get_context_data(**kwargs)
        context['page'] = context.get('page_obj')  # dirty hack for current template
        return context

    def get_queryset(self):
        iid = self.kwargs.get('iid')
        self.sort_by = self.request.GET.get('sort', "mod_desc")
        if self.sort_by not in paginate_sort_opts.keys():
            self.sort_by = "mod_desc"

        self.workgroup = get_object_or_404(MDR.Workgroup, pk=iid)
        # self.check_user_permission()
        return MDR._concept.objects.filter(workgroup=iid).select_subclasses().order_by(
            *paginate_sort_opts.get(self.sort_by))


class MembersView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, DetailView):
    template_name = 'aristotle_mdr/user/workgroups/members.html'
    permission_required = "aristotle_mdr.view_workgroup"


class ArchiveView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, DetailView):
    template_name = 'aristotle_mdr/actions/archive_workgroup.html'
    permission_required = "aristotle_mdr.can_archive_workgroup"

    def post(self, request, *args, **kwargs):
        self.workgroup = self.get_object()
        self.workgroup.archived = not self.workgroup.archived
        self.workgroup.save()
        return HttpResponseRedirect(self.workgroup.get_absolute_url())


class AddMembersView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, FormView):
    template_name = 'aristotle_mdr/actions/addWorkgroupMember.html'
    form_class = MDRForms.workgroups.AddMembers
    permission_required = "aristotle_mdr.change_workgroup"

    pk_url_kwarg = 'iid'

    def get_context_data(self, **kwargs):
        kwargs.update({
            'role': self.request.GET.get('role')
        })
        return super().get_context_data(**kwargs)

    def get_object(self):
        return self.get_workgroup()

    def get_workgroup(self):
        pk = self.kwargs.get(self.pk_url_kwarg)
        workgroup = get_object_or_404(Workgroup, pk=pk)
        return workgroup

    def form_valid(self, form):
        user = form.cleaned_data['user']
        role = form.cleaned_data['role']
        self.get_workgroup().giveRoleToUser(role, user)

        return redirect(self.get_success_url())

    def get_initial(self):
        return {'roles': self.request.GET.getlist('role')}

    def get_success_url(self):
        return reverse("aristotle:workgroupMembers", args=[self.get_object().pk])


class LeaveView(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, DetailView):
    template_name = 'aristotle_mdr/actions/workgroup_leave.html'
    permission_required = "aristotle_mdr.can_leave_workgroup"

    def post(self, request, *args, **kwargs):
        self.get_object().removeUser(request.user)
        return HttpResponseRedirect(reverse("aristotle:userHome"))


class CreateWorkgroup(LoginRequiredMixin, PermissionRequiredMixin, UserFormViewMixin, CreateView):
    model = MDR.Workgroup
    form_class = MDRForms.workgroups.CreateWorkgroupForm
    user_form = True
    template_name = "aristotle_mdr/user/workgroups/add.html"
    raise_exception = True
    redirect_unauthenticated_users = True
    permission_required = "aristotle_mdr.user_can_create_workgroup"


class ListWorkgroup(PermissionRequiredMixin, GenericListWorkgroup):
    template_name = "aristotle_mdr/user/workgroups/list_all.html"
    permission_required = "aristotle_mdr.is_registry_administrator"
    raise_exception = True

    def get_initial_queryset(self):
        return MDR.Workgroup.objects.all()


class EditWorkgroup(LoginRequiredMixin, WorkgroupContextMixin, ObjectLevelPermissionRequiredMixin, UpdateView):
    template_name = "aristotle_mdr/user/workgroups/edit.html"
    permission_required = "aristotle_mdr.change_workgroup"

    fields = [
        'name',
        'definition',
    ]

    context_object_name = "item"


class ChangeUserRoles(SingleRoleChangeView):
    model = MDR.Workgroup
    template_name = "aristotle_mdr/user/workgroups/change_role.html"
    permission_required = "aristotle_mdr.change_workgroup"
    form_class = MDRForms.workgroups.ChangeWorkgroupUserRolesForm
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    def get_success_url(self):
        return redirect(reverse('aristotle:workgroupMembers', args=[self.get_object().id]))


class RemoveUser(MemberRemoveFromGroupView):
    model = MDR.Workgroup
    template_name = "aristotle_mdr/user/workgroups/remove_member.html"
    permission_required = "aristotle_mdr.change_workgroup"
    pk_url_kwarg = 'iid'
    context_object_name = "item"

    def get_success_url(self):
        return redirect(reverse('aristotle:workgroupMembers', args=[self.get_object().id]))


class WorkgroupURLManager(GroupURLManager):
    # TODO: Acually use this
    group_context_name = "workgroup"


def workgroup_backend_factory(*args, **kwargs):
    # TODO: Acually use this
    kwargs.update({
        "group_class": MDR.Workgroup,
        "membership_class": MDR.WorkgroupMembership,
        "namespace": "aristotle_mdr:workgroup",
        "update_fields": ['definition']
    })

    return WorkgroupURLManager(*args, **kwargs)
