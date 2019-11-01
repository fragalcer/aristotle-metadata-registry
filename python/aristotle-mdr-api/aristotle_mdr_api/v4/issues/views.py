from rest_framework import generics
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from aristotle_mdr.contrib.issues.models import Issue, IssueComment
from . import serializers
from aristotle_mdr_api.v4.permissions import AuthCanViewEdit
from aristotle_mdr import perms


class IssueView(generics.RetrieveUpdateAPIView):
    """Retrieve and update and issue"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.IssueSerializer
    queryset = Issue.objects.all()


class IssueCreateView(generics.CreateAPIView):
    """Create a new issue"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.IssueSerializer


class IssueCommentCreateView(generics.CreateAPIView):
    """Create a comment against an issue"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.IssueCommentSerializer


class IssueCommentRetrieveView(generics.RetrieveAPIView):
    """Retrieve an issue comment"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.IssueCommentSerializer
    queryset = IssueComment.objects.all()


class IssueAPIView(APIView):
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    pk_url_kwarg = 'pk'

    issue_serializer = serializers.IssueSerializer

    def get_object(self):
        pk = self.kwargs[self.pk_url_kwarg]
        obj = get_object_or_404(Issue, pk=pk)
        if not perms.user_can(self.request.user, obj, 'can_alter_open'):
            raise PermissionDenied
        return obj

    def alter_open_issue(self, issue, commit=False):
        serializer_context = {'request': self.request}
        # Setup issue serializer for partial update
        issue_serializer = self.issue_serializer(
            instance=issue,
            data={'isopen': self.request.data['isopen']},
            partial=True,
            context=serializer_context
        )
        # Check valid
        issue_serializer.is_valid(raise_exception=True)
        # Save if requested
        if commit:
            return issue_serializer.save()
        return issue_serializer


class IssueUpdateAndCommentView(IssueAPIView):
    """Open or close an issue, with optional comment"""
    issue_serializer = serializers.IssueSerializer
    comment_serializer = serializers.IssueCommentSerializer

    def post(self, request, *args, **kwargs):
        obj = self.get_object()

        if 'isopen' not in request.data:
            return Response(
                status=status.HTTP_400_BAD_REQUEST
            )

        issue_serializer = self.alter_open_issue(obj)

        response_content = {}

        if 'comment' in request.data:
            # Process comment
            commentdata = request.data['comment']
            commentdata['issue'] = obj.pk

            comment_serializer = self.comment_serializer(
                data=commentdata,
                context={'request': request}
            )
            comment_serializer.is_valid(raise_exception=True)
            comment_serializer.save()
            response_content['comment'] = comment_serializer.data

        # Save issue
        issue = issue_serializer.save()
        # Set response data
        response_content['issue'] = issue_serializer.data

        return Response(
            response_content,
            status=status.HTTP_200_OK,
        )


class IssueApproveView(IssueAPIView):

    def post(self, request, *args, **kwargs):
        obj = self.get_object()

        if 'isopen' not in request.data:
            return Response(
                status=status.HTTP_400_BAD_REQUEST
            )

        issue_serializer = self.alter_open_issue(obj)

        # Apply change to item if user has permission
        if not perms.user_can_edit(request.user, obj.item):
            raise PermissionDenied

        # Make changes
        obj.apply()
        issue_serializer.save()

        return Response(status=status.HTTP_200_OK)
