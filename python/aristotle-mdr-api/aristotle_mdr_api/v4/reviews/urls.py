from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r'(?P<pk>\d+)/promote-concept/$', views.PromoteImpactedItemToReviewItemsView.as_view(), name='promote_concept'),
    re_path(r'(?P<pk>\d+)/remove-concept/$', views.RemoveItemFromReviewItemsView.as_view(), name='remove_concept'),
    re_path(r'(?P<pk>\d+)/updatecomment/$', views.ReviewUpdateAndCommentView.as_view(), name='update_and_comment'),
    re_path(r'comments/$', views.ReviewCommentCreateView.as_view(), name='comment'),
    re_path(r'comments/(?P<pk>\d+)/$', views.ReviewCommentRetrieveView.as_view(), name='comment_get'),
]
