from django.urls import path
from . import views

urlpatterns = [
    path('comments/', views.ReviewCommentCreateView.as_view(), name='comment'),
    path('comments/<int:pk>/', views.ReviewCommentRetrieveView.as_view(), name='comment_get'),
    path('<int:pk>/promote-concept/', views.PromoteImpactedItemToReviewItemsView.as_view(), name='promote_concept'),
    path('<int:pk>/remove-concept/', views.RemoveItemFromReviewItemsView.as_view(), name='remove_concept'),
    path('<int:pk>/update-comment/', views.ReviewUpdateAndCommentView.as_view(), name='update_and_comment'),
]
