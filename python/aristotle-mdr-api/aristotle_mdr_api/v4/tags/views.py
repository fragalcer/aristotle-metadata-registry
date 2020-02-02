from rest_framework import generics
from rest_framework.schemas import ManualSchema, AutoSchema
from coreapi import Field
from aristotle_mdr_api.v4.permissions import AuthCanViewEdit
from aristotle_mdr_api.v4.tags import serializers
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import Http404
from drf_yasg.utils import swagger_auto_schema

from aristotle_mdr.contrib.favourites.models import Tag, Favourite
from aristotle_mdr.models import _concept
from aristotle_mdr.perms import user_can_view


class TagView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve and update a tag"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.TagSerializer
    queryset = Tag.objects.all()


class ItemTagUpdateView(generics.UpdateAPIView):
    """Update tags for a specific item"""
    permission_classes = (AuthCanViewEdit,)
    permission_key = 'metadata'
    serializer_class = serializers.ItemTagSerializer
    pk_url_kwarg = 'iid'

    def dispatch(self, request, *args, **kwargs):
        item_id = self.kwargs[self.pk_url_kwarg]
        self.item = get_object_or_404(_concept, pk=item_id)
        return super().dispatch(request, *args, **kwargs)

    @swagger_auto_schema(auto_schema=None)
    def patch(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    def get_object(self):
        if not user_can_view(self.request.user, self.item):
            raise PermissionDenied

        return Favourite.objects.filter(
            tag__profile=self.request.user.profile,
            tag__primary=False,
            item=self.item
        ).select_related('tag')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['item'] = self.item
        return context
