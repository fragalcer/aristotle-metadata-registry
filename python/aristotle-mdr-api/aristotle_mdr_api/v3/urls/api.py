from django.conf.urls import include, url
from ..views import concepts, views, concepttypes, about
from rest_framework import routers
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from aristotle_mdr_api.v3.generators import AristotleV3SchemaGenerator

# Create a router and register our viewsets with it.
router = routers.DefaultRouter()
router.register(r'metadata', concepts.ConceptViewSet)
router.register(r'types', concepttypes.ConceptTypeViewSet)
router.register(r'search', views.SearchViewSet, basename="search")
router.register(r'ras', views.RegistrationAuthorityViewSet)
router.register(r'organizations', views.OrganizationViewSet)
router.register(r'superseded_by', concepts.SupersededRelationshipViewSet)
# router.register(r'about', about.About)

schema_view = get_schema_view(
    openapi.Info(
        title="Aristotle API",
        default_version='v3',
        description="Aristotle API",
        license=openapi.License(name="BSD License"),
    ),
    generator_class=AristotleV3SchemaGenerator,
    public=True,
    permission_classes=(permissions.AllowAny,),
    urlconf='aristotle_mdr_api.v3.urls'
)

urlpatterns = [
    url(r'^about/$', about.About.as_view()),
    url(r'^schema(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^$', schema_view.with_ui('swagger', cache_timeout=0), name='schema'),
    url(r'^', include(router.urls)),
]
