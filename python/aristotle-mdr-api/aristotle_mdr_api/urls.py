from django.conf.urls import include, url
from django.utils.module_loading import import_string
from .views import APIRootView
# from rest_framework.authtoken import views as tokenviews


API_TITLE = 'Aristotle MDR API'
API_DESCRIPTION = """
---

The Aristotle Metadata Registry API is a standardised way to access metadata through a consistent
machine-readable interface.

"""


urlpatterns = [
    url(r'^auth/', include(('rest_framework.urls', 'rest_framework'), namespace='rest_framework')),
    # url(r'^api-token-auth/', tokenviews.obtain_auth_token),
    url(r'^token/', include(('aristotle_mdr_api.token_auth.urls', 'aristotle_mdr_api.token_auth'), namespace='token_auth')),
    url(r'^$', APIRootView.as_view(), name="aristotle_api_root"),
    url(r'^v3/', include(('aristotle_mdr_api.v3.urls', 'aristotle_mdr_api.v3'), namespace='aristotle_mdr_api.v3')),
    url(r'^v4/', include(('aristotle_mdr_api.v4.urls', 'aristotle_mdr_api.v4'), namespace='api_v4')),
]
