import notifications.urls

from django.urls import include, re_path
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.views.generic.base import RedirectView

from aristotle_mdr.views.user_pages import FriendlyLoginView, FriendlyLogoutView
from aristotle_mdr.contrib.user_management.views import AristotlePasswordResetView

admin.autodiscover()

urlpatterns = [
    re_path(r'^login/?$', FriendlyLoginView.as_view(), name='friendly_login'),
    re_path(r'^logout/?$', FriendlyLogoutView.as_view(), name='logout'),
    re_path(r'^django/admin/doc/', include('django.contrib.admindocs.urls')),
    re_path(r'^django/admin/', admin.site.urls),
    re_path(r'^ckeditor/', include('aristotle_mdr.urls.ckeditor_uploader')),
    re_path(r'^account/notifications/', include((notifications.urls, 'notifications'), namespace="notifications")),
    re_path(r'^account/password/reset/$', AristotlePasswordResetView.as_view()),
    re_path(r'^account/password/reset_done/$', AristotlePasswordResetView.as_view()),
    re_path(r'^user/password/reset/$',
            AristotlePasswordResetView.as_view(),
            {'post_reset_redirect': '/user/password/reset/done/'},
            name="password_reset",
            ),
    re_path(r'^user/password/reset/done/$',
            auth_views.PasswordResetDoneView.as_view(),
            name="password_reset_done",
            ),
    re_path(r'^user/password/reset/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$',
            auth_views.PasswordResetConfirmView.as_view(),
            name='password_reset_confirm',
            ),
    re_path(r'^user/password/done/$', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    re_path(r'^account/password/?$', RedirectView.as_view(url='account/home/', permanent=True)),
    re_path(r'^account/password/change/?$', auth_views.PasswordChangeView.as_view(), name='password_change'),
    re_path(r'^account/password/change/done/?$', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    re_path(r'', include('user_sessions.urls', 'user_sessions')),
]
