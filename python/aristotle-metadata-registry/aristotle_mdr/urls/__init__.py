from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

admin.autodiscover()

urlpatterns = [
    url(r'^', include(('aristotle_mdr.contrib.issues.urls', 'aristotle_mdr.contrib.issues'), namespace='aristotle_issues')),
    url(r'^', include(('aristotle_mdr.contrib.publishing.urls', 'aristotle_mdr_publishing'), namespace="aristotle_publishing")),
    url(r'^', include('aristotle_mdr.urls.base')),
    url(r'^browse/', include('aristotle_mdr.contrib.browse.urls')),
    url(r'^favourites/', include(('aristotle_mdr.contrib.favourites.urls', 'aristotle_mdr.contrib.favourites'), namespace='aristotle_favourites')),
    url(r'^help/', include(('aristotle_mdr.contrib.help.urls', 'aristotle_help'), namespace="aristotle_help")),
    url(r'^', include(('aristotle_bg_workers.urls', 'aristotle_bg_workers'), namespace='aristotle_bg_workers')),
    url(r'^', include(('aristotle_mdr.contrib.user_management.urls', 'aristotle_mdr.contrib.user_management'), namespace='aristotle-user')),
    url(r'^', include(('aristotle_mdr.urls.aristotle', 'aristotle_mdr'), namespace="aristotle")),
    url(r'^ac/', include(('aristotle_mdr.contrib.autocomplete.urls', 'aristotle_mdr.contrib.autocomplete'), namespace='aristotle-autocomplete')),
    url(r'^', include(('aristotle_mdr.contrib.healthcheck.urls', 'aristotle_mdr_hb'), namespace="aristotle_hb")),
    url(r'^', include('aristotle_mdr.contrib.view_history.urls')),
    url(r'^', include(('aristotle_mdr.contrib.reviews.urls', 'aristotle_mdr_review_requests'), namespace="aristotle_reviews")),
    url(r'^', include(('aristotle_mdr.contrib.custom_fields.urls', 'aristotle_mdr.contrib.custom_fields'), namespace='aristotle_custom_fields')),
    url(r'^', include(('aristotle_mdr.contrib.validators.urls', 'aristotle_mdr.contrib.validators'), namespace='aristotle_validations')),
    url(r'^api/', include('aristotle_mdr_api.urls'))
]

if settings.DEBUG:
    from aristotle_mdr.views import debug as debug_views
    urlpatterns += [
        url(r'^aristotle_debug/(pdf|word|html|slow)/$', debug_views.download, name='api_mark_all_read'),
    ]

handler403 = 'aristotle_mdr.views.unauthorised'
handler404 = 'aristotle_mdr.views.not_found'
handler500 = 'aristotle_mdr.views.handler500'
