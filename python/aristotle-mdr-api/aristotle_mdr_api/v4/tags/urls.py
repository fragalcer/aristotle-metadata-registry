from django.urls import re_path
from aristotle_mdr_api.v4.tags import views

urlpatterns = [
    re_path(r'item/(?P<iid>\d+)/$', views.ItemTagUpdateView.as_view(), name='item_tags'),
    re_path(r'(?P<pk>\d+)/$', views.TagView.as_view(), name='tags'),
]
