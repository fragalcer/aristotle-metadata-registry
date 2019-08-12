import notifications.urls

from django.conf.urls import include, url
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.views.generic.base import RedirectView

from aristotle_mdr.views.user_pages import FriendlyLoginView, FriendlyLogoutView
from aristotle_mdr.contrib.user_management.views import AristotlePasswordResetView

admin.autodiscover()

urlpatterns = [
    url(r'^login/?$', FriendlyLoginView.as_view(), name='friendly_login'),
    url(r'^logout/?$', FriendlyLogoutView.as_view(), name='logout'),
    url(r'^django/admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^django/admin/', admin.site.urls),
    url(r'^ckeditor/', include('aristotle_mdr.urls.ckeditor_uploader')),
    url(r'^account/notifications/', include((notifications.urls, 'notifications'), namespace="notifications")),
    url(r'^account/password/reset/$', AristotlePasswordResetView.as_view()),
    url(r'^account/password/reset_done/$', AristotlePasswordResetView.as_view()),
    url(
        r'^user/password/reset/$',
        AristotlePasswordResetView.as_view(),
        {'post_reset_redirect': '/user/password/reset/done/'},
        name="password_reset"
    ),
    url(
        r'^user/password/reset/done/$',
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done"
    ),
    url(
        r'^user/password/reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
        auth_views.PasswordResetConfirmView.as_view(),
        {'post_reset_redirect': '/user/password/done/'},
        name='password_reset_confirm',
    ),
    url(r'^user/password/done/$', auth_views.PasswordResetCompleteView.as_view()),
    url(r'^account/password/?$', RedirectView.as_view(url='account/home/', permanent=True)),
    url(r'^account/password/change/?$', auth_views.PasswordChangeView.as_view(), name='password_change'),
    url(r'^account/password/change/done/?$', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    url(r'', include('user_sessions.urls', 'user_sessions')),
]
