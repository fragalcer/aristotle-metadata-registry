from django.urls import re_path
from aristotle_mdr_api.v4.custom_fields import views

urlpatterns = [
    re_path(r'(?P<pk>\d+)/$', views.CustomFieldRetrieveView.as_view(), name='custom_field_get'),
    re_path(r'list/$', views.CustomFieldListView.as_view(), name='custom_field_list')
]
