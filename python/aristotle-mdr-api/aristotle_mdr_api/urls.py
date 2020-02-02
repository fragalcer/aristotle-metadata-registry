from django.urls import re_path, include
from .views import APIRootView
# from rest_framework.authtoken import views as tokenviews


API_TITLE = 'Aristotle MDR API'
API_DESCRIPTION = """
---

The Aristotle Metadata Registry API is a standardised way to access metadata through a consistent
machine-readable interface.

"""


urlpatterns = [
    re_path(r'^auth/', include(('rest_framework.urls', 'rest_framework'), namespace='rest_framework')),
    # re_path(r'^api-token-auth/', tokenviews.obtain_auth_token),
    re_path(r'^token/', include(('aristotle_mdr_api.token_auth.urls', 'aristotle_mdr_api.token_auth'), namespace='token_auth')),
    re_path(r'^$', APIRootView.as_view(), name="aristotle_api_root"),
    re_path(r'^v3/', include(('aristotle_mdr_api.v3.urls', 'aristotle_mdr_api.v3'), namespace='aristotle_mdr_api.v3')),
    re_path(r'^v4/', include(('aristotle_mdr_api.v4.urls', 'aristotle_mdr_api.v4'), namespace='api_v4')),
]
