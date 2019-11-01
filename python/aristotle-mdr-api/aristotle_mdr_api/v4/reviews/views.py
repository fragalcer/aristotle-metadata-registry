from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from aristotle_mdr.contrib.reviews.models import ReviewComment, ReviewRequest
from aristotle_mdr_api.v4.permissions import AuthCanViewEdit
from aristotle_mdr import perms
import aristotle_mdr.models as MDR

from . import serializers


class ReviewCommentCreateView(generics.CreateAPIView):
    """Create a comment against a review"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.ReviewCommentSerializer


class ReviewCommentRetrieveView(generics.RetrieveAPIView):
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.ReviewCommentSerializer
    queryset = ReviewComment.objects.all()


class ReviewUpdateAndCommentView(generics.UpdateAPIView):
    """Open or close a review, with optional comment"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.ReviewUpdateAndCommentSerializer
    pk_url_kwarg = 'pk'

    http_method_names = ['patch']

    def get_object(self):
        pk = self.kwargs[self.pk_url_kwarg]
        obj = get_object_or_404(ReviewRequest, pk=pk)
        if not perms.user_can_close_or_reopen_review(self.request.user, obj):
            raise PermissionDenied
        return obj


class AlterItemInReviewView(APIView):
    operation_flag = ''

    def put(self, request, *args, **kwargs):
        if self.operation_flag == '':
            raise AssertionError("An operation flag must be set")

        review_request = get_object_or_404(ReviewRequest, pk=kwargs.get('pk'))

        if not review_request.can_edit(request.user):
            raise PermissionDenied

        concept_id = int(request.data['concept_id'])

        if self.operation_flag == 'add':
            review_request.concepts.add(MDR._concept.objects.get(pk=concept_id))
            return Response(data={"concept_id": concept_id}, status=status.HTTP_200_OK)

        elif self.operation_flag == 'remove':
            review_request.concepts.remove(MDR._concept.objects.get(pk=concept_id))
            return Response(data={"concept_id": concept_id}, status=status.HTTP_200_OK)

        else:
            raise AssertionError("Flag must be set to either add or remove")


class PromoteImpactedItemToReviewItemsView(AlterItemInReviewView):
    operation_flag = 'add'


class RemoveItemFromReviewItemsView(AlterItemInReviewView):
    operation_flag = 'remove'
