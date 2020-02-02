from django.urls import re_path
from aristotle_mdr_api.v4.rules import views

urlpatterns = [
    re_path(r'ra/$', views.CreateRARules.as_view(), name='create_ra_rules'),
    re_path(r'ra/(?P<pk>\d+)/$', views.RetrieveUpdateRARules.as_view(), name='ra_rules'),
    re_path(r'registry/$', views.RetrieveUpdateRegistryRules.as_view(), name='registry_rules'),
]
