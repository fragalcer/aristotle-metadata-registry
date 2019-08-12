from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.urls import reverse_lazy

from haystack.views import search_view_factory

import aristotle_mdr.views as views
from aristotle_mdr.views.search import PermissionSearchView
import aristotle_mdr.forms as forms
import aristotle_mdr.models as models
from aristotle_mdr.contrib.generic.views import (
    GenericAlterOneToManyView,
    GenericAlterManyToManyView,
    GenericAlterManyToManyOrderView,
    generic_foreign_key_factory_view
)

from django.utils.translation import ugettext_lazy as _

urlpatterns = [
    url(r'^$', views.SmartRoot.as_view(
        unauthenticated_pattern='aristotle_mdr:home',
        authenticated_pattern='aristotle_mdr:userHome'
    ), name='smart_root'),
    url(r'^home/?$', TemplateView.as_view(template_name='aristotle_mdr/static/home.html'), name="home"),
    url(r'^manifest.json$', TemplateView.as_view(template_name='meta/manifest.json', content_type='application/json')),
    url(r'^robots.txt$', TemplateView.as_view(template_name='meta/robots.txt', content_type='text/plain')),
    url(r'^sitemap.xml$', views.sitemaps.main, name='sitemap_xml'),
    url(r'^sitemaps/sitemap_(?P<page>[0-9]+).xml$', views.sitemaps.page_range, name='sitemap_range_xml'),

    url(r'^steward', include(('aristotle_mdr.contrib.stewards.urls', 'aristotle_mdr.contrib.stewards'), namespace='stewards')),

    # all the below take on the same form:
    # all the below take on the same form:
    # url(r'^itemType/(?P<iid>\d+)?/?
    # Allowing for a blank ItemId (iid) allows aristotle to redirect to /about/itemtype instead of 404ing

    url(r'^conceptualdomain/(?P<iid>\d+)?/edit/values/?$',
        GenericAlterOneToManyView.as_view(
            model_base=models.ConceptualDomain,
            model_to_add=models.ValueMeaning,
            model_base_field='valuemeaning_set',
            model_to_add_field='conceptual_domain',
            ordering_field='order',
            form_add_another_text=_('Add a value meaning'),
            form_title=_('Change Value Meanings')
        ), name='value_meanings_edit'),

    url(r'^item/(?P<iid>\d+)?/alter_relationship/(?P<fk_field>[A-Za-z\-_]+)/?$',
        generic_foreign_key_factory_view,
        name='generic_foreign_key_editor'),

    url(r'^workgroup/(?P<iid>\d+)(?:-(?P<name_slug>[A-Za-z0-9\-_]+))?/?$', views.workgroups.WorkgroupView.as_view(), name='workgroup'),
    url(r'^workgroup/(?P<iid>\d+)/members/?$', views.workgroups.MembersView.as_view(), name='workgroupMembers'),
    url(r'^workgroup/(?P<iid>\d+)/items/?$', views.workgroups.ItemsView.as_view(), name='workgroupItems'),
    url(r'^workgroup/(?P<iid>\d+)/leave/?$', views.workgroups.LeaveView.as_view(), name='workgroup_leave'),
    url(r'^workgroup/(?P<iid>\d+)/add_member$', views.workgroups.AddMembersView.as_view(), name='addWorkgroupMembers'),
    url(r'^workgroup/(?P<iid>\d+)/change_roles/(?P<user_pk>\d+)/?$', views.workgroups.ChangeUserRoles.as_view(), name='workgroup_member_change_role'),
    url(r'^workgroup/(?P<iid>\d+)/remove/(?P<user_pk>\d+)/?$', views.workgroups.RemoveUser.as_view(), name='workgroup_member_remove'),
    url(r'^workgroup/(?P<iid>\d+)/archive/?$', views.workgroups.ArchiveView.as_view(), name='archive_workgroup'),
    url(r'^workgroup/(?P<iid>\d+)/edit$', views.workgroups.EditWorkgroup.as_view(), name='workgroup_edit'),
    url(r'^workgroups/create/?$', views.workgroups.CreateWorkgroup.as_view(), name='workgroup_create'),
    url(r'^workgroups/all/?$', views.workgroups.ListWorkgroup.as_view(), name='workgroup_list'),

    url(r'^discussions/?$', views.discussions.All.as_view(), name='discussions'),
    url(r'^discussions/new/?$', views.discussions.New.as_view(), name='discussionsNew'),
    url(r'^discussions/workgroup/(?P<wgid>\d+)/?$', views.discussions.Workgroup.as_view(), name='discussionsWorkgroup'),
    url(r'^discussions/post/(?P<pid>\d+)/?$', views.discussions.Post.as_view(), name='discussionsPost'),
    url(r'^discussions/post/(?P<pid>\d+)/newcomment/?$', views.discussions.NewComment.as_view(), name='discussionsPostNewComment'),
    url(r'^discussions/delete/comment/(?P<cid>\d+)/?$', views.discussions.DeleteComment.as_view(), name='discussionsDeleteComment'),
    url(r'^discussions/delete/post/(?P<pid>\d+)/?$', views.discussions.DeletePost.as_view(), name='discussionsDeletePost'),
    url(r'^discussions/edit/comment/(?P<cid>\d+)/?$', views.discussions.EditComment.as_view(), name='discussionsEditComment'),
    url(r'^discussions/edit/post/(?P<pid>\d+)/?$', views.discussions.EditPost.as_view(), name='discussionsEditPost'),
    url(r'^discussions/post/(?P<pid>\d+)/toggle/?$', views.discussions.TogglePost.as_view(), name='discussionsPostToggle'),

    url(r'^item/(?P<iid>\d+)/edit/?$', views.editors.EditItemView.as_view(), name='edit_item'),
    url(r'^item/(?P<iid>\d+)/clone/?$', views.editors.CloneItemView.as_view(), name='clone_item'),
    url(r'^item/(?P<iid>\d+)/graphs/?$', views.tools.ItemGraphView.as_view(), name='item_graphs'),
    url(r'^item/(?P<iid>\d+)/related/(?P<relation>.+)?$', views.tools.ConceptRelatedListView.as_view(), name='item_related'),
    url(r'^item/(?P<iid>\d+)/compare_fields/?$', views.versions.CompareHTMLFieldsView.as_view(), name='compare_fields'),
    url(r'^item/(?P<iid>\d+)/history/$', views.versions.ConceptVersionListView.as_view(), name='item_history'),
    url(r'^item/(?P<iid>\d+)/compare/?$', views.versions.ConceptVersionCompareView.as_view(), name='compare_versions'),
    url(r'^item/(?P<iid>\d+)/registrationHistory/?$', views.registrationHistory, name='registrationHistory'),
    url(r'^item/(?P<iid>\d+)/child_states/?$', views.actions.CheckCascadedStates.as_view(), name='check_cascaded_states'),

    # Concept page overrides
    url(r'^item/(?P<iid>\d+)/dataelement/(?P<name_slug>.+)/?$', views.DataElementView.as_view(), name='dataelement'),
    url(r'^item/(?P<iid>\d+)/objectclass/(?P<name_slug>.+)/?$', views.ObjectClassView.as_view(), name='objectclass_view'),
    url(r'^item/(?P<iid>\d+)(?:/(?P<model_slug>\w+)/(?P<name_slug>.+))?/?$', views.ConceptView.as_view(), name='item'),
    url(r'^item/(?P<iid>\d+)(?:/.*)?$', views.ConceptView.as_view(), name='item_short'),  # Catch every other 'item' URL and throw it for a redirect
    url(r'^item/(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?(.*)?$', views.concept_by_uuid, name='item_uuid'),

    url(r'^unmanaged/measure/(?P<iid>\d+)(?:/(?P<model_slug>\w+)/(?P<name_slug>.+))?/?$', views.MeasureView.as_view(), name='measure'),
    url(r"^managed_items/(?P<model_slug>.+)/(?P<iid>.+)?$", view=views.ManagedItemView.as_view(), name="view_managed_item"),

    # url(r'^create/?$', views.item, name='item'),
    url(r'^create/?$', views.create_list, name='create_list'),
    url(r'^create/wizard/aristotle_mdr/dataelementconcept$', views.wizards.DataElementConceptWizard.as_view(), name='createDataElementConcept'),
    url(r'^create/wizard/aristotle_mdr/dataelement$', views.wizards.DataElementWizard.as_view(), name='createDataElement'),
    url(r'^create/(?P<app_label>.+)/(?P<model_name>.+)/?$', views.wizards.create_item, name='createItem'),
    url(r'^create/(?P<model_name>.+)/?$', views.wizards.create_item, name='createItem'),

    url(r'^download/options/(?P<download_type>\w+)/?$', views.downloads.DownloadOptionsView.as_view(), name='download_options'),
    url(r'^download/bulk/(?P<download_type>\w+)/?$', views.downloads.BulkDownloadView.as_view(), name='bulk_download'),
    url(r'^download/(?P<download_type>\w+)/(?P<iid>\d+)/?$', views.downloads.DownloadView.as_view(), name='download'),
    url(r'^dlstatus/(?P<taskid>[a-z0-9\-]+)/?$',
        views.downloads.DownloadStatusView.as_view(),
        name='download_status',
        ),

    url(r'^action/supersede/(?P<iid>\d+)$', views.actions.SupersedeItemView.as_view(), name='supersede'),
    url(r'^action/proposed/supersede/(?P<iid>\d+)$', views.actions.ProposedSupersedeItemView.as_view(), name='proposed_supersede'),

    url(r'^action/bulkaction/?$', views.bulk_actions.BulkAction.as_view(), name='bulk_action'),
    url(r'^action/bulkaction/state/?$', views.bulk_actions.ChangeStatusBulkActionView.as_view(), name='change_state_bulk_action'),
    url(r'^toolbox/compare/?$', views.comparator.MetadataComparison.as_view(), name='compare_concepts'),
    url(r'^toolbox/dataelementcomponents/?$', views.tools.DataElementsAndSubcomponentsStatusCheckTool.as_view(), name='data_element_components_tool'),

    url(r'^action/changestatus/(?P<iid>\d+)$', views.ChangeStatusView.as_view(), name='changeStatus'),
    url(r'^action/deletestatus/(?P<sid>\d+)/(?P<iid>\d+)$', views.DeleteStatus.as_view(), name='deleteStatus'),
    url(r'^action/editstatus/(?P<sid>\d+)/item/(?P<iid>\d+)/registrationauthority/(?P<raid>\w+)$', views.EditStatus.as_view(), name='editStatus'),

    url(r'^account/?$', RedirectView.as_view(url=reverse_lazy("aristotle:userHome"), permanent=True)),
    url(r'^account/home/?$', views.user_pages.home, name='userHome'),
    url(r'^account/sandbox/?$', views.user_pages.SandboxedItemsView.as_view(), name='userSandbox'),
    url(r'^account/sandbox/delete/?$', views.actions.DeleteSandboxView.as_view(), name="sandbox_delete"),
    url(r'^account/roles/?$', views.user_pages.Roles.as_view(), name='userRoles'),
    url(r'^account/admin/?$', views.user_pages.admin_tools, name='userAdminTools'),
    url(r'^account/admin/statistics/?$', views.user_pages.admin_stats, name='userAdminStats'),
    url(r'^account/edit/?$', views.user_pages.EditView.as_view(), name='userEdit'),
    url(r'^account/notificationpermissions/?$', views.user_pages.NotificationPermissions.as_view(), name='notificationPermissions'),
    url(r'^account/profile/?$', views.user_pages.ProfileView.as_view(), name='userProfile'),
    url(r'^account/recent/?$', views.user_pages.recent, name='userRecentItems'),
    url(r'^account/workgroups/?$', views.user_pages.MyWorkgroupList.as_view(), name='userWorkgroups'),
    url(r'^account/workgroups/archives/?$', views.user_pages.WorkgroupArchiveList.as_view(), name='user_workgroups_archives'),
    url(r'^account/notifications/?$', views.user_pages.InboxView.as_view(), name='userInbox'),
    url(r'^account/notifications-all/?$', views.user_pages.InboxViewAll.as_view(), name='userInboxAll'),
    url(r'^account/notifications/api/mark-all-as-read/', views.notify.MarkAllReadApiView.as_view(), name='api_mark_all_read'),

    url(r'^account/django/(.*)?$', views.user_pages.django_admin_wrapper, name='django_admin'),

    url(r'^account/registrartools/?$', views.user_pages.RegistrarTools.as_view(), name='userRegistrarTools'),

    url(r'^registrationauthority/create/?$', views.registrationauthority.CreateRegistrationAuthority.as_view(), name='registrationauthority_create'),
    url(r'^account/admin/registrationauthority/all/?$', views.registrationauthority.ListRegistrationAuthorityAll.as_view(), name='registrationauthority_list'),

    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/data_dictionary', views.registrationauthority.DateFilterView.as_view(), name='registrationauthority_data_dictionary'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/members', views.registrationauthority.MembersRegistrationAuthority.as_view(), name='registrationauthority_members'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/edit', views.registrationauthority.EditRegistrationAuthority.as_view(), name='registrationauthority_edit'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/states', views.registrationauthority.EditRegistrationAuthorityStates.as_view(), name='registrationauthority_edit_states'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/rules', views.registrationauthority.RAValidationRuleEditView.as_view(), name='registrationauthority_rules'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/add_user/?$', views.registrationauthority.AddUser.as_view(), name='registrationauthority_add_user'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/change_roles/(?P<user_pk>\d+)?/?$', views.registrationauthority.ChangeUserRoles.as_view(), name='registrationauthority_change_user_roles'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/remove/(?P<user_pk>\d+)/?$', views.registrationauthority.RemoveUser.as_view(), name='registrationauthority_member_remove'),
    url(r'^registrationauthority/(?P<iid>\d+)(?:/(?P<name_slug>.+))?/', views.registrationauthority.RegistrationAuthorityView.as_view(), name='registrationAuthority'),

    url(r'^organization/(?P<iid>\d+)?(?:/(?P<name_slug>.+))?/?$', views.registrationauthority.organization, name='organization'),
    url(r'^organizations/?$', views.registrationauthority.all_organizations, name='all_organizations'),
    url(r'^registrationauthorities/?$', views.registrationauthority.all_registration_authorities, name='all_registration_authorities'),

    url(r'^extensions/?$', views.extensions, name='extensions'),

    url(r'^notifyredirect/(?P<content_type>\d+)/(?P<object_id>\d+)/', views.notification_redirect, name="notify_redirect"),

    url(r'^about/aristotle/?$', TemplateView.as_view(template_name='aristotle_mdr/static/aristotle_mdr.html'), name="aboutMain"),
    url(r'^about/(?P<template>.+)/?$', views.DynamicTemplateView.as_view(), name="about"),

    url(r'^accessibility/?$', TemplateView.as_view(template_name='aristotle_mdr/static/accessibility.html'), name="accessibility"),

    url(r'user/(?P<uid>\d+)/profilePicture', views.user_pages.profile_picture, name="profile_picture"),
    url(r'user/(?P<uid>\d+)/profilePicture.svg', views.user_pages.profile_picture, name="dynamic_profile_picture"),

    url(r'share/(?P<share>[\w-]+)$', views.user_pages.SharedSandboxView.as_view(), name='sharedSandbox'),
    url(r'share/(?P<share>[\w-]+)/(?P<iid>\d+)', views.user_pages.SharedItemView.as_view(), name='sharedSandboxItem'),

    url(r'version/(?P<verid>\d+)', views.versions.ConceptVersionView.as_view(), name='item_version'),

    url(
        r'^search/?$',
        search_view_factory(
            view_class=PermissionSearchView,
            template='search/search.html',
            searchqueryset=None,
            form_class=forms.search.PermissionSearchForm
        ),
        name='search'
    ),
]
