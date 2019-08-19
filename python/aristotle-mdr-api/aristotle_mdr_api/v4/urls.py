from django.conf.urls import include, url

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from aristotle_mdr_api.v4.generators import AristotleSchemaGenerator

schema_view = get_schema_view(
    openapi.Info(
        title="Aristotle API",
        default_version='v4',
        description="Aristotle API",
        license=openapi.License(name="BSD License"),
    ),
    generator_class=AristotleSchemaGenerator,
    public=True,
    permission_classes=(permissions.AllowAny,),
    urlconf='aristotle_mdr_api.v4.urls'
)

urlpatterns = [
    url(r'^custom_fields/', include('aristotle_mdr_api.v4.custom_fields.urls')),
    url(r'^issues/', include(('aristotle_mdr_api.v4.issues.urls', 'aristotle_mdr_api.v4.issues'), namespace='issues')),
    url(r'^item/', include(('aristotle_mdr_api.v4.concepts.urls', 'aristotle_mdr_api.v4.concepts'), namespace='item')),
    url(r'^reviews/', include(('aristotle_mdr_api.v4.reviews.urls', 'aristotle_mdr_api.v4.reviews'), namespace='reviews')),
    url(r'^tags/', include('aristotle_mdr_api.v4.tags.urls')),
    url(r'^rules/', include('aristotle_mdr_api.v4.rules.urls')),
    url(r'^schema(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^$', schema_view.with_ui('swagger', cache_timeout=0), name='schema'),
]
