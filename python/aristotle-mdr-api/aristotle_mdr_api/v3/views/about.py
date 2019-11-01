from rest_framework.views import APIView
from rest_framework.response import Response

from django.utils.module_loading import import_string
from aristotle_mdr.utils import fetch_aristotle_settings


class About(APIView):
    """
    Gives basic details about the registry
    """

    def get(self, request, format=None):
        """
        Gives basic details about the registry
        """
        
        settings = fetch_aristotle_settings()

        about = {
            'name': settings['SITE_NAME'],
            'description': settings['SITE_DESCRIPTION'],
            'version': "1.6",
            'installed_apps': [],
            'aristotle_mdr': {
                'version': import_string("aristotle_mdr.__version__"),
            }
        }
        return Response(about)
