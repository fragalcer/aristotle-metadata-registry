from django.urls import path
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

from ckeditor_uploader import views

urlpatterns = [
    path('upload/', login_required(views.upload), name='ckeditor_upload'),
    path('browse/', never_cache(login_required(views.browse)), name='ckeditor_browse'),
]
