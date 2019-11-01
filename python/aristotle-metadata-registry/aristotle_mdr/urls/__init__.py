from django.conf import settings
from django.urls import re_path, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = [
    re_path(r'^', include(('aristotle_mdr.contrib.issues.urls', 'aristotle_mdr.contrib.issues'), namespace='aristotle_issues')),
    re_path(r'^', include(('aristotle_mdr.contrib.publishing.urls', 'aristotle_mdr_publishing'), namespace="aristotle_publishing")),
    re_path(r'^', include('aristotle_mdr.urls.base')),
    re_path(r'^browse/', include('aristotle_mdr.contrib.browse.urls')),
    re_path(r'^favourites/', include(('aristotle_mdr.contrib.favourites.urls', 'aristotle_mdr.contrib.favourites'), namespace='aristotle_favourites')),
    re_path(r'^help/', include(('aristotle_mdr.contrib.help.urls', 'aristotle_help'), namespace="aristotle_help")),
    re_path(r'^', include(('aristotle_bg_workers.urls', 'aristotle_bg_workers'), namespace='aristotle_bg_workers')),
    re_path(r'^', include(('aristotle_mdr.contrib.user_management.urls', 'aristotle_mdr.contrib.user_management'), namespace='aristotle-user')),
    re_path(r'^', include(('aristotle_mdr.urls.aristotle', 'aristotle_mdr'), namespace="aristotle")),
    re_path(r'^ac/', include(('aristotle_mdr.contrib.autocomplete.urls', 'aristotle_mdr.contrib.autocomplete'), namespace='aristotle-autocomplete')),
    re_path(r'^', include('aristotle_mdr.contrib.view_history.urls')),
    re_path(r'^', include(('aristotle_mdr.contrib.reviews.urls', 'aristotle_mdr_review_requests'), namespace="aristotle_reviews")),
    re_path(r'^', include(('aristotle_mdr.contrib.custom_fields.urls', 'aristotle_mdr.contrib.custom_fields'), namespace='aristotle_custom_fields')),
    re_path(r'^', include(('aristotle_mdr.contrib.validators.urls', 'aristotle_mdr.contrib.validators'), namespace='aristotle_validations')),
    re_path(r'^api/', include('aristotle_mdr_api.urls'))
]

if settings.DEBUG:
    from aristotle_mdr.views import debug as debug_views
    urlpatterns += [
        re_path(r'^aristotle_debug/(pdf|word|html|slow)/$', debug_views.download, name='api_mark_all_read'),
    ]

handler403 = 'aristotle_mdr.views.unauthorised'
handler404 = 'aristotle_mdr.views.not_found'
handler500 = 'aristotle_mdr.views.handler500'
