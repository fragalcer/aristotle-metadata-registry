from django.urls import re_path
from aristotle_mdr_api.v4.concepts import views


urlpatterns = [
    re_path(r'^(?P<pk>\d+)/update-permissions/$', views.UpdateVersionPermissionsView.as_view(), name="update-version-permissions"),
    re_path(r'^(?P<pk>\d+)/view-permission/(?P<vpk>\d+)/$', views.GetVersionsPermissionsView.as_view(), name='view-version-permissions'),
    re_path(r'(?P<pk>\d+)/$', views.ConceptView.as_view(), name='item'),
    re_path(r'^(?P<pk>\d+)/supersedes-graphical/$', views.SupersedesGraphicalConceptView.as_view(), name='item_supersedes_graphical'),
    re_path(r'^(?P<pk>\d+)/general-graphical/$', views.GeneralGraphicalConceptView.as_view(), name='item_general_graphical'),
    re_path(r'^(?P<pk>\d+)/links-graphical/$', views.ConceptLinksView.as_view(), name='api_item_links'),
    re_path(r'^(?P<pk>\d+)/list-versions/$', views.ListVersionsView.as_view(), name="list-versions"),
    re_path(r'^(?P<pk>\d+)/list-permissions/$', views.ListVersionsPermissionsView.as_view(), name="list-version-permissions"),
]
