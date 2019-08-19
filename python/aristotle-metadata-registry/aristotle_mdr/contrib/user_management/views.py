from braces.views import LoginRequiredMixin, PermissionRequiredMixin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from organizations.backends.defaults import BaseBackend
from organizations.backends.tokens import RegistrationTokenGenerator

from aristotle_mdr.utils.utils import fetch_aristotle_settings
from aristotle_mdr.views.utils import ObjectLevelPermissionRequiredMixin
from aristotle_mdr.views.user_pages import (
    EditView as EditUserView,
    ProfileView
)
from . import forms


class AristotlePasswordResetView(PasswordResetView):
    from_email = settings.ARISTOTLE_EMAIL_ACCOUNT_RECOVERY


class AnotherUserMixin(LoginRequiredMixin, ObjectLevelPermissionRequiredMixin):
    raise_exception = True
    redirect_unauthenticated_users = True
    permission_required = "aristotle_mdr.view_other_users_account"

    def get_success_url(self):
        return reverse('aristotle-user:view_another_user', args=[self.kwargs['user_pk']])

    def get_user(self, querySet=None):
        return get_user_model().objects.get(pk=self.kwargs['user_pk'])

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({
            'object': self.get_user(),
        })
        return context

    def get_object(self, querySet=None):
        # We need this here for object level permissions to work
        return self.get_user()


class UpdateAnotherUser(AnotherUserMixin, EditUserView):
    template_name = "aristotle_mdr/users_management/users/update_another_user.html"


class ViewAnotherUser(AnotherUserMixin, ProfileView):
    template_name = "aristotle_mdr/users_management/users/view_another_user.html"


class UpdateAnotherUserSiteWidePerms(AnotherUserMixin, FormView):
    template_name = "aristotle_mdr/users_management/users/update_another_user_site_perms.html"
    form_class = forms.UpdateAnotherUserSiteWidePermsForm
    permission_required = "aristotle_mdr.list_registry_users"

    def get_initial(self):
        user = self.get_user()
        initial = {
            "is_superuser": user.is_superuser,
            "is_staff": user.is_staff,
            "perm_view_all_metadata": user.perm_view_all_metadata,
        }
        return initial

    def form_valid(self, form):
        user = self.get_user()
        with transaction.atomic():
            # Maybe wrap inside reversion.revisions.create_revision() later
            user.is_superuser = form.cleaned_data['is_superuser']
            user.is_staff = form.cleaned_data['is_staff']
            user.perm_view_all_metadata = form.cleaned_data['perm_view_all_metadata']
            user.save()
        return super().form_valid(form)


class RegistryOwnerUserList(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name='aristotle_mdr/users_management/users/list.html'

    permission_required = "aristotle_mdr.list_registry_users"
    raise_exception = True
    redirect_unauthenticated_users = True
    paginate_by = 50

    def get_queryset(self):
        q = self.request.GET.get('q', None)
        queryset = get_user_model().objects.all().order_by(
            '-is_active', 'full_name', 'short_name', 'email'
        )
        if q:
            queryset = queryset.filter(
                Q(short_name__icontains=q) |
                Q(full_name__icontains=q) |
                Q(email__icontains=q)
            )
        return queryset


class DeactivateRegistryUser(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name='aristotle_mdr/users_management/users/deactivate.html'

    permission_required = "aristotle_mdr.deactivate_registry_users"
    raise_exception = True
    redirect_unauthenticated_users = True

    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        deactivated_user = self.kwargs.get('user_pk')
        deactivated_user = get_object_or_404(get_user_model(), pk=deactivated_user)
        deactivated_user.is_active = False
        deactivated_user.save()
        return redirect(reverse("aristotle-user:registry_user_list"))

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        deactivate_user = self.kwargs.get('user_pk')
        if not deactivate_user:
            raise Http404

        deactivate_user = get_object_or_404(get_user_model(), pk=deactivate_user)

        data['deactivate_user'] = deactivate_user
        return data


class ReactivateRegistryUser(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name='aristotle_mdr/users_management/users/reactivate.html'

    permission_required = "aristotle_mdr.reactivate_registry_users"
    raise_exception = True
    redirect_unauthenticated_users = True

    http_method_names = ['get', 'post']

    def post(self, request, *args, **kwargs):
        reactivated_user = self.kwargs.get('user_pk')
        reactivated_user = get_object_or_404(get_user_model(), pk=reactivated_user)
        reactivated_user.is_active = True
        reactivated_user.save()
        return redirect(reverse("aristotle-user:registry_user_list"))

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        reactivate_user = self.kwargs.get('user_pk')
        if not reactivate_user:
            raise Http404

        reactivate_user = get_object_or_404(get_user_model(), pk=reactivate_user)

        data['reactivate_user'] = reactivate_user
        return data


class SignupMixin:

    activation_subject = 'aristotle_mdr/users_management/newuser/email/activation_subject.txt'
    activation_body = 'aristotle_mdr/users_management/newuser/email/activation_body.html'

    def __init__(self, *args, **kwargs):
        self.registration_backend = BaseBackend()
        super().__init__(*args, **kwargs)

    def send_activation(self, user):
        # Send Activation Email
        token = self.registration_backend.get_token(user)
        self.registration_backend.email_message(
            user,
            self.activation_subject,
            self.activation_body,
            token=token,
            user_id=user.id,
            accept_url_name=self.accept_url_name,
            config=fetch_aristotle_settings(),
            request=self.request
        ).send()

    def get_signup_settings(self, request):
        aristotle_settings = fetch_aristotle_settings()

        try:
            signup_settings = aristotle_settings['SELF_SIGNUP']
        except KeyError:
            signup_settings = None

        if signup_settings:
            # Check if user self signup is enabled
            self.signup_enabled = signup_settings.get('enabled', False)
            self.allowed_suffixes = signup_settings.get('emails', None)
        else:
            self.signup_enabled = False
            self.allowed_suffixes = None

        return self.signup_enabled

    def send_password_reset(self, user_email, request):

        if settings.ARISTOTLE_EMAIL_ACCOUNT_RECOVERY:
            from_email = settings.ARISTOTLE_EMAIL_ACCOUNT_RECOVERY
        else:
            from_email = settings.DEFAULT_FROM_EMAIL

        form = PasswordResetForm({'email': user_email})
        if form.is_valid():
            form.save(
                request=request,
                from_email=from_email,
                use_https=True
            )
            return True
        else:
            return False


class SignupView(SignupMixin, FormView):

    form_class = forms.UserRegistrationForm
    template_name = "aristotle_mdr/users_management/self_invite.html"
    accept_url_name = 'aristotle-user:signup_activate'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_model = get_user_model()
        self.if_logged_in_url = reverse('aristotle_mdr:userHome')

    def get_context_data(self, *args, **kwargs):
        kwargs.update({'resend_button': True})
        return super().get_context_data(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.if_logged_in_url)

        self.get_signup_settings(request)

        if not self.signup_enabled:
            return self.render_to_response({'error_message': 'Self Signup is not enabled'})

        return super().dispatch(request, *args, **kwargs)

    def validate_email(self, email, suffixes):
        valid = False

        for suffix in suffixes:
            if email.endswith(suffix.strip()):
                valid = True

        return valid

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance with the passed
        POST variables and then checked for validity.
        """
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        email = form.data['email']
        existing_user = self.user_model.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_active:
                self.send_password_reset(existing_user.email, self.request)
            else:
                self.send_activation(existing_user)

            # Show message
            return self.render_to_response(
                context={'message': 'Success, an activation link has been sent to your email. Follow the link to continue'}
            )

        return super().form_invalid(form)

    def form_valid(self, form):
        success = True

        email = form.cleaned_data['email']

        # If email suffix whitelist was setup
        if self.allowed_suffixes:
            email_valid = self.validate_email(email, self.allowed_suffixes)
            if not email_valid:
                form.add_error('email', 'Email is not at an allowed url')
                success = False

        if success:
            user = form.save(commit=False)
            user.email = form.cleaned_data['email']

            # # Validate unique
            # unique = True
            # try:
            #     user.validate_unique()
            # except ValidationError:
            #     unique = False

            # if unique:
            if True:
                # Save inactive user
                user.set_password(form.cleaned_data['password'])
                user.is_active = False
                user.save()

                # Send Activation Email
                self.send_activation(user)
            # else:
            #     # Send password reset email
            #     existing = self.user_model.objects.get(email=user.email)

            #     if existing.is_active:
            #         self.send_password_reset(user.email, self.request)
            #     else:
            #         self.send_activation(existing)

            # Show message
            return self.render_to_response(
                context={'message': 'Success, an activation link has been sent to your email. Follow the link to continue'}
            )
        else:
            return self.form_invalid(form)


class SignupActivateView(SignupMixin, TemplateView):

    template_name = "aristotle_mdr/users_management/self_invite.html"

    admin_notification_subject = 'aristotle_mdr/users_management/newuser/email/admin_notification_subject.txt'
    admin_notification_body = 'aristotle_mdr/users_management/newuser/email/admin_notification_body.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_generator = RegistrationTokenGenerator()
        self.user_model = get_user_model()
        self.success_redirect = reverse('friendly_login') + '?welcome=true'
        self.users_to_notify = self.user_model.objects.filter(is_superuser=True)

    def dispatch(self, request, *args, **kwargs):
        self.get_signup_settings(request)

        if not self.signup_enabled:
            return self.signup_disabled_message()

        return super().dispatch(request, *args, **kwargs)

    def signup_disabled_message(self):
        return self.render_to_response({'error_message': 'Self Signup is not enabled'})

    def signup_error_message(self):
        return self.render_to_response({
            'error_message': 'Account could not be activated',
            'resend_button': True
        })

    def notify_of_activation(self, user_email):
        for user in self.users_to_notify:
            self.registration_backend.email_message(
                user,
                self.admin_notification_subject,
                self.admin_notification_body,
                user_email=user_email,
                config=fetch_aristotle_settings(),
            ).send()

    def get(self, request, *args, **kwargs):

        user_id = self.kwargs.get('user_id', None)
        token = self.kwargs.get('token', None)

        if not user_id or not token:
            return self.signup_error_message()

        try:
            user = self.user_model.objects.get(id=user_id, is_active=False)
        except self.user_model.DoesNotExist:
            return self.signup_error_message()

        if self.token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            self.notify_of_activation(user.email)
            return HttpResponseRedirect(self.success_redirect)

        return self.signup_error_message()


class ResendActivationView(SignupMixin, FormView):

    template_name = "aristotle_mdr/users_management/self_invite.html"
    form_class = forms.ResendActivationForm
    accept_url_name = 'aristotle-user:signup_activate'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({
            'title': 'Resend Activation',
            'button_text': 'Resend'
        })
        return context

    def form_valid(self, form):

        email = form.cleaned_data['email']
        user_model = get_user_model()

        try:
            user = user_model.objects.get(email=email, is_active=False)
        except user_model.DoesNotExist:
            user = None

        if user:
            self.send_activation(user)

        return self.render_to_response(
            {'message': 'If you have singed up with the email previously an activation link has been sent to your email. Follow the link to continue'}
        )
