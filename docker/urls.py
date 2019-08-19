from django.conf import settings
from django.conf.urls import include, url


urlpatterns = [
    url(r'^alias/', include('impersonate.urls')),
    url(r'^api/', include('aristotle_mdr_api.urls')),
    url(r'^', include(('aristotle_dse.urls', "aristotle_dse"), namespace="aristotle_dse")),
    url(r'^', include(('aristotle_mdr.contrib.links.urls', "aristotle_mdr_links"), namespace="aristotle_mdr_links")),
    url(r'^', include(('aristotle_mdr.contrib.slots.urls', "aristotle_slots"), namespace="aristotle_slots")),
    url(r'^', include(('aristotle_mdr.contrib.identifiers.urls', "aristotle_mdr_identifiers"), namespace="aristotle_identifiers")),
    url(r'^', include('aristotle_mdr.urls')),
    url(r'^', include(('aristotle_mdr.contrib.links.urls', 'aristotle_mdr_links'), namespace="aristotle_mdr_links")),
    url(r'^comet/', include(('comet.urls', 'comet'), namespace='comet')),
    url(r'^glossary/', include(('aristotle_glossary.urls', "aristotle_glossary"), namespace="aristotle_glossary"))
]


if settings.DEBUG and settings.DEBUG_TOOLBAR:
    import debug_toolbar
    urlpatterns.append(url(r'^__debug__/', include(debug_toolbar.urls)))


# This is only for dev work, so we can skip it.
if settings.DEBUG:  # pragma: no cover
    from django.contrib.staticfiles import views

    urlpatterns += [
        url(r'^static/(?P<path>.*)$', views.serve),
    ]

    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
