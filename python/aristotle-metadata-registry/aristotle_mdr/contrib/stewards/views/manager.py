from django.conf.urls import url
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView
)
from django.urls import reverse

from aristotle_mdr.contrib.groups.backends import (
    GroupURLManager, GroupMixin, HasRolePermissionMixin,
)
from aristotle_mdr import models as MDR
from aristotle_mdr.utils.model_utils import ManagedItem
from aristotle_mdr.views.workgroups import GenericListWorkgroup
from aristotle_mdr.views.registrationauthority import ListRegistrationAuthorityBase

from . import views
from aristotle_mdr.contrib.stewards.views.utils import get_aggregate_count_of_collection
from aristotle_mdr.contrib.stewards.models import Collection
from aristotle_mdr.contrib.stewards.views.collections import EditCollectionViewBase

import logging

logger = logging.getLogger(__name__)


class StewardGroupMixin(GroupMixin):
    group_class = MDR.StewardOrganisation


class ListCollectionsBase(ListView):
    model = Collection


class ManagedItemViewMixin:

    def get_model_class(self, request):
        model_name = self.kwargs.get("model_name").lower()
        self.model = ContentType.objects.get(model=model_name).model_class()
        if not issubclass(self.model, ManagedItem):
            raise Http404
        return self.model

    def dispatch(self, request, *args, **kwargs):
        self.model = self.get_model_class(request)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs.update({
            "model": self.model,
            "model_name": self.model._meta.verbose_name.title(),
        })
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        self.model = self.get_model_class(self.request)
        self.queryset = self.model.objects.all().visible(self.request.user).order_by("name")
        return super().get_queryset()


class StewardURLManager(GroupURLManager):
    group_context_name = "stewardship_organisation"

    def get_extra_group_urls(self):
        return [
            url("browse", view=self.browse_view(), name="browse"),
            url("workgroups/$", view=self.workgroup_list_view(), name="workgroups"),
            url("workgroups/create/$", view=self.workgroup_create_view(), name="workgroups_create"),

            url("managed_items/?$", view=self.managed_item_list_types(), name="managed_item_list_types"),
            url("managed_items/(?P<model_name>[^\/]+)/?$", view=self.managed_item_list_items(), name="managed_item_list_items"),
            url("managed_items/(?P<model_name>.+)/create/?$", view=self.managed_item_create_view(), name="create_managed_item"),
            url("managed_items/(?P<model_name>.+)/(?P<mi_pk>.+)/edit/?$", view=self.managed_item_edit_view(), name="edit_managed_item"),
            url("ras/$", view=self.registration_authority_list_view(), name="registrationauthorities"),

            url("collections/$", view=self.collection_list_view(), name="collections"),
            url("collections/create$", view=self.collection_create_view(), name="collections_create"),
            url("collection/(?P<pk>\d+)$", view=self.collection_detail_view(), name="collection_detail_view"),
            url("collection/(?P<pk>\d+)/edit$", view=self.collection_edit_view(), name="collection_edit_view"),
            url("collection/(?P<pk>\d+)/delete", view=self.collection_delete_view(), name="collection_delete"),

        ]

    def list_all_view(self, *args, **kwargs):
        return views.ListStewardOrg.as_view(manager=self, model=self.group_class, *args, **kwargs)

    def workgroup_list_view(self):

        class ListWorkgroup(StewardGroupMixin, HasRolePermissionMixin, GenericListWorkgroup):
            current_group_context = "workgroups"
            role_permission = "list_workgroups"
            template_name = "aristotle_mdr/user/workgroups/steward_list.html"
            raise_exception = True

            def get_initial_queryset(self):
                return self.get_group().workgroup_set.all()

        return ListWorkgroup.as_view(manager=self, group_class=self.group_class)

    def workgroup_create_view(self):
        from aristotle_mdr.views.workgroups import CreateWorkgroup as Base

        class CreateWorkgroup(HasRolePermissionMixin, StewardGroupMixin, Base):
            role_permission = "manage_workgroups"

            def get_initial(self):
                initial = super().get_initial()
                initial['stewardship_organisation'] = self.get_group()
                return initial

        return CreateWorkgroup.as_view(manager=self, group_class=self.group_class)

    def registration_authority_list_view(self):
        class ListRegistrationAuthorities(StewardGroupMixin, HasRolePermissionMixin, ListRegistrationAuthorityBase):
            current_group_context = "registrationauthorities"
            role_permission = "view_group"
            template_name = "aristotle_mdr/user/registration_authority/steward_list.html"
            raise_exception = True

            def get_queryset(self):
                return self.get_group().registrationauthority_set.all()

        return ListRegistrationAuthorities.as_view(manager=self, group_class=self.group_class)

    def collection_list_view(self):
        class ListCollectionsView(StewardGroupMixin, HasRolePermissionMixin, ListCollectionsBase):
            current_group_context = "collections"
            role_permission = "view_group"
            template_name = "aristotle_mdr/collections/steward_list.html"
            raise_exception = True

            def get_queryset(self):
                return self.get_group().collection_set.filter(parent_collection__isnull=True).all().visible(self.request.user).order_by('name')

        return ListCollectionsView.as_view(manager=self, group_class=self.group_class)

    def collection_detail_view(self):
        class DetailCollectionsView(StewardGroupMixin, HasRolePermissionMixin, DetailView):
            current_group_context = "collections"
            role_permission = "view_group"
            template_name = "aristotle_mdr/collections/details.html"
            raise_exception = True
            context_object_name = "item"
            model = Collection

            def get_queryset(self):
                return self.get_group().collection_set.visible(self.request.user).all()

            def get_context_data(self, *args, **kwargs):
                context = super().get_context_data(*args, **kwargs)

                context['sub_collections'] = self.get_object().collection_set.visible(user=self.request.user).order_by('name')

                metadata = self.get_object().metadata.all().select_subclasses().visible(user=self.request.user).order_by('name')

                context['metadata'] = metadata
                context['type_counts'] = get_aggregate_count_of_collection(metadata)

                return context

        return DetailCollectionsView.as_view(manager=self, group_class=self.group_class)

    def collection_create_view(self):
        class CreateCollectionView(EditCollectionViewBase, CreateView):
            template_name = "aristotle_mdr/collections/add.html"

            def get_initial(self):
                initial = super().get_initial()
                initial['stewardship_organisation'] = self.get_group()
                return initial

        return CreateCollectionView.as_view(manager=self, group_class=self.group_class)

    def collection_edit_view(self):
        class UpdateCollectionView(EditCollectionViewBase, UpdateView):
            template_name = "aristotle_mdr/collections/edit.html"

        return UpdateCollectionView.as_view(manager=self, group_class=self.group_class)

    def collection_delete_view(self):

        class DeleteCollectionView(EditCollectionViewBase, DeleteView):
            template_name = "aristotle_mdr/collections/delete.html"

            def get_success_url(self):
                messages.success(
                    self.request,
                    "Collection '{}' delete successfully".format(self.get_object().name)
                )
                return reverse('aristotle:stewards:group:collections', args=[self.get_group().slug])

        return DeleteCollectionView.as_view(manager=self, group_class=self.group_class)

    def browse_view(self):
        from aristotle_mdr.contrib.browse.views import BrowseConcepts

        class Browse(StewardGroupMixin, BrowseConcepts):
            current_group_context = "metadata"
            model = MDR._concept

            def get_queryset(self, *args, **kwargs):
                qs = super().get_queryset(*args, **kwargs)
                return qs.filter(stewardship_organisation=self.get_group())

            def get_context_data(self, *args, **kwargs):
                # Call the base implementation first to get a context
                self.kwargs['app'] = "aristotle_mdr"
                context = super().get_context_data(*args, **kwargs)
                return context

            def get_template_names(self):
                return ['stewards/metadata/list.html']

        return Browse.as_view(manager=self, group_class=self.group_class)

    def managed_item_create_view(self):
        class CreateManagedItemView(StewardGroupMixin, ManagedItemViewMixin, CreateView):
            template_name = "stewards/managed_item/add.html"
            role_permission = "manage_managed_items"
            fields=["stewardship_organisation", "name", "definition"]

            def get_initial(self):
                initial = super().get_initial()
                initial['stewardship_organisation'] = self.get_group()
                return initial

        return CreateManagedItemView.as_view(manager=self, group_class=self.group_class)

    def managed_item_edit_view(self):
        class UpdateManagedItemView(StewardGroupMixin, ManagedItemViewMixin, UpdateView):
            template_name = "stewards/managed_item/edit.html"
            role_permission = "manage_managed_items"
            fields=["name", "definition"]
            pk_url_kwarg = "mi_pk"

        return UpdateManagedItemView.as_view(manager=self, group_class=self.group_class)

    def managed_item_list_types(self):
        class ListManagedItemTypesList(StewardGroupMixin, HasRolePermissionMixin, ListView):
            current_group_context = "managed"
            role_permission = "view_group"
            template_name = "stewards/managed_item/list_types.html"
            raise_exception = True

            def get_queryset(self):
                types = [
                    x for x in ContentType.objects.all()
                    if x.model_class() and issubclass(x.model_class(), ManagedItem)
                ]
                for t in types:
                    t.item_count = t.model_class().objects.filter(
                        stewardship_organisation=self.get_group()
                    ).visible(self.request.user).count()
                return types

        return ListManagedItemTypesList.as_view(manager=self, group_class=self.group_class)

    def managed_item_list_items(self):
        class ListManagedItems(StewardGroupMixin, HasRolePermissionMixin, ManagedItemViewMixin, ListView):
            current_group_context = "managed"
            role_permission = "view_group"
            template_name = "stewards/managed_item/list_items.html"
            raise_exception = True
            paginate_by = 50

        return ListManagedItems.as_view(manager=self, group_class=self.group_class)


def group_backend_factory(*args, **kwargs):
    kwargs.update({
        "group_class": MDR.StewardOrganisation,
        "membership_class": MDR.StewardOrganisationMembership,
        "namespace": "aristotle_mdr:stewards:group",
        "update_fields": ['description']
    })

    return StewardURLManager(*args, **kwargs)
