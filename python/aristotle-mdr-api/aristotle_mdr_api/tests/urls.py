from django.urls import include, path, re_path

urlpatterns = [
    re_path(r'^', include('aristotle_mdr.urls')),
    path('browse/', include('aristotle_mdr.contrib.browse.urls')),
    path('help/', include(('aristotle_mdr.contrib.help.urls', "aristotle_help"), namespace="aristotle_help")),
    path('api/', include('aristotle_mdr_api.urls'))
]
