from braces.views import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from aristotle_mdr.contrib.issues.models import IssueLabel
from aristotle_mdr.contrib.issues.forms import IssueLabelEditForm
from aristotle_mdr.views.utils import UserFormViewMixin
from aristotle_mdr.views.utils import ObjectLevelPermissionRequiredMixin


class IssueLabelBase:
    model = IssueLabel
    success_url = reverse_lazy("aristotle_issues:admin_issue_label_list")


class IssueLabelList(PermissionRequiredMixin, IssueLabelBase, ListView):
    template_name = 'aristotle_mdr/issues/admin/labels_list.html'
    permission_required = "aristotle_mdr.can_alter_any_issue_labels"
    redirect_unauthenticated_users = True
    raise_exception = True


class IssueLabelCreate(PermissionRequiredMixin, UserFormViewMixin, IssueLabelBase, CreateView):
    template_name = 'aristotle_mdr/issues/admin/labels_create.html'
    permission_required = "aristotle_mdr.can_alter_any_issue_labels"
    form_class = IssueLabelEditForm
    redirect_unauthenticated_users = True
    raise_exception = True


class IssueLabelUpdate(ObjectLevelPermissionRequiredMixin, UserFormViewMixin, IssueLabelBase, UpdateView):
    template_name = 'aristotle_mdr/issues/admin/labels_update.html'
    permission_required = "aristotle_mdr.user_can_edit_issue_label"
    form_class = IssueLabelEditForm
    redirect_unauthenticated_users = True
    raise_exception = True


class IssueLabelDelete(ObjectLevelPermissionRequiredMixin, UserFormViewMixin, IssueLabelBase, DeleteView):
    template_name = 'aristotle_mdr/issues/admin/labels_delete.html'
    permission_required = "aristotle_mdr.user_can_edit_issue_label"
    redirect_unauthenticated_users = True
    raise_exception = True
