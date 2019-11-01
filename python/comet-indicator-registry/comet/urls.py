from django.urls import re_path

from comet import views
from django.views.generic import TemplateView


urlpatterns = [
    re_path(r'^/?$', TemplateView.as_view(template_name='comet/static/about_comet_mdr.html')),

    # These are required for about pages to work. Include them, or custom items will die!
    re_path(r'^about/(?P<template>.+)/?$', views.DynamicTemplateView.as_view(), name="about"),
    re_path(r'^about/?$', TemplateView.as_view(template_name='comet/static/about_comet_mdr.html'), name="about"),
]
