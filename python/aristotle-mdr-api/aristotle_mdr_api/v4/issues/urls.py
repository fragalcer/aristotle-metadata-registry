from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r'^$', views.IssueCreateView.as_view(), name='create'),
    re_path(r'^(?P<pk>\d+)/$', views.IssueView.as_view(), name='issue'),
    re_path(r'^(?P<pk>\d+)/updatecomment/$', views.IssueUpdateAndCommentView.as_view(), name='update_and_comment'),
    re_path(r'^(?P<pk>\d+)/approve/$', views.IssueApproveView.as_view(), name='approve'),
    re_path(r'^comments/$', views.IssueCommentCreateView.as_view(), name='comment'),
    re_path(r'^comments/(?P<pk>\d+)/$', views.IssueCommentRetrieveView.as_view(), name='comment_get'),
]
