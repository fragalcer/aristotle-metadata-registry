import notifications
import autocomplete_light
# import every app/autocomplete_light_registry.py
autocomplete_light.autodiscover()

from django.conf.urls import patterns, include, url
from django.contrib.auth.views import password_reset
from django.contrib import admin
from django.views.generic.base import RedirectView
from aristotle_mdr.views.user_pages import friendly_redirect_login
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^', include('aristotle_mdr.urls.base')),
    url(r'^', include('aristotle_mdr.urls.aristotle', app_name="aristotle_mdr", namespace="aristotle")),
)
handler403 = 'aristotle_mdr.views.unauthorised'
