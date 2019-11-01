from django.urls import path
from . import views
from aristotle_mdr.utils import get_concept_models
from aristotle_mdr_api.v4.metadata.utils import create_model_api_class_dynamically
from aristotle_mdr_api.v4.metadata.views import ListCreateMetadataAPIView, RetrieveUpdateMetadataAPIView


def create_metadata_urls_dynamically():
    """
    This function generates a list of valid Django URLs each of them containing a custom View class.
    The main purpose of this function is to generate serializers for the Swagger API endpoints, and
    provide a frontend graphical representation of the serializers.
    None of these endpoints are actually used, because the metadata_type parameter of the
    list_or_create_metadata_endpoint is actually overridden by the model_name of each one of the
    dynamically-generated urls.
    :return: List of paths.
    """
    list_of_urls = []
    for model in get_concept_models():
        model_name = model.__name__.lower()
        list_of_urls.extend([
            path(model_name,
                 create_model_api_class_dynamically(
                     model,
                     (ListCreateMetadataAPIView,)
                 ).as_view(),
                 name='list_or_create_metadata_endpoint_' + model_name),
            path(model_name + '/<uuid:item_uuid>',
                 create_model_api_class_dynamically(
                     model,
                     (RetrieveUpdateMetadataAPIView,)
                 ).as_view(),
                 name='retrieve_update_metadata_endpoint_' + model_name),
        ])
    return list_of_urls


urlpatterns = [
    path('<uuid:item_uuid>', views.GetMetadataTypeFromUuidAndRedirect.as_view(), name='get_metadata_type_from_uuid'),
] + create_metadata_urls_dynamically()
