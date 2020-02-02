from rest_framework import generics, status
from rest_framework.reverse import reverse
from django.template.defaultfilters import slugify
from django.http.response import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.utils.text import get_text_list
from aristotle_mdr.contrib.serializers.concept_serializer import ConceptSerializerFactory
from aristotle_mdr.models import _concept
from aristotle_mdr_api.v3.views.utils import ConceptResultsPagination
from aristotle_mdr_api.v4.permissions import UnAuthenticatedUserCanView
from aristotle_mdr.utils import get_concept_models


import logging
logger = logging.getLogger(__name__)


class GetMetadataTypeFromUuidAndRedirect(generics.RetrieveAPIView):
    """
    The purpose of this API Endpoint is to retrieve the item type from a uuid parameter and redirect to a
    generic metadata serialiser API Endpoint handler.
    """
    permission_classes = (UnAuthenticatedUserCanView,)

    def dispatch(self, request, *args, **kwargs):
        item_uuid = kwargs.get("item_uuid")
        item = get_object_or_404(_concept, uuid=item_uuid)

        return HttpResponseRedirect(
            redirect_to=reverse(
                "api_v4:metadata:retrieve_update_metadata_endpoint_{}".format(slugify(item.item_type.model)),
                kwargs={
                    "item_uuid": item_uuid,
                }
            )
        )


class GenericMetadataSerialiserAPIView(generics.RetrieveAPIView):
    """
    The purpose of this API Endpoint is to retrieve a serialized representation of a _concept metadata child instance.
    """

    lookup_field = 'uuid'
    lookup_url_kwarg = 'item_uuid'
    permission_classes = (UnAuthenticatedUserCanView,)

    def dispatch(self, request, *args, **kwargs):

        metadata_type = kwargs.get("metadata_type")

        self.klass = None
        concept_models = get_concept_models()
        concept_model_names = []
        for model in concept_models:
            model_name = slugify(model.__name__)
            concept_model_names.append(model_name)
            if model_name == metadata_type:
                self.klass = model
        if self.klass is None:
            msg = _('Argument metadata_type provided does not exist.')
            return JsonResponse(
                data={
                    "API Error message": msg,
                    "Possible fields include": get_text_list(concept_model_names, _("or"))
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.klass.objects.all()

    def get_serializer(self, instance, *args, **kwargs):
        serializer_class = ConceptSerializerFactory().generate_serializer_class(self.klass)
        return serializer_class(instance)


class ListCreateMetadataAPIView(generics.ListCreateAPIView):
    lookup_field = 'uuid'
    lookup_url_kwarg = 'item_uuid'
    pagination_class = ConceptResultsPagination
    permission_classes = (UnAuthenticatedUserCanView,)


class RetrieveUpdateMetadataAPIView(generics.RetrieveUpdateAPIView):
    lookup_field = 'uuid'
    lookup_url_kwarg = 'item_uuid'
    permission_classes = (UnAuthenticatedUserCanView,)
