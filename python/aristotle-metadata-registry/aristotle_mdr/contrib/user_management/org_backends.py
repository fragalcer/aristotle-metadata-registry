from braces.views import LoginRequiredMixin, PermissionRequiredMixin

from django.conf.urls import url
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.views.generic import FormView
from django.template import loader

from organizations.backends.defaults import (
    InvitationBackend,
    RegistrationBackend
)

from organizations.backends.tokens import RegistrationTokenGenerator

from . import forms

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils.translation import ugettext_lazy as _

from django.http import Http404

from aristotle_mdr.utils.utils import fetch_aristotle_settings

import logging
logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class BaseAristotleInvitationBackend(InvitationBackend):
    """
    A backend for allowing new users to join the site by creating a new user
    associated with a new organization.
    """

    form_class = forms.UserRegistrationForm
    accept_url_name = 'registry_invitations_register'

    def get_success_url(self):
        return reverse('friendly_login') + '?welcome=true'

    def get_urls(self):
        return [
            url(r'^accept/(?P<user_id>[\d]+)-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
                view=self.activate_view, name=self.accept_url_name),
            url(r'^$', view=self.invite_view(), name="registry_invitations_create"),
        ]

    def invite_view(self):
        """
        Initiates the organization and user account creation process
        """
        return InviteView.as_view(backend=self)

    def activate_view(self, request, user_id, token):
        """
        View function that activates the given User by setting `is_active` to
        true if the provided information is verified.
        """
        try:
            user = self.user_model.objects.get(id=user_id, is_active=False)
        except self.user_model.DoesNotExist:
            raise Http404(_("Your URL may have expired."))
        if not RegistrationTokenGenerator().check_token(user, token):
            raise Http404(_("Your URL may have expired."))

        form = self.get_form(data=request.POST or None, instance=user)
        if form.is_valid():
            form.instance.is_active = True
            user = form.save()
            user.set_password(form.cleaned_data['password'])
            user.save()
            self.activate_organizations(user)
            return redirect(self.get_success_url())
        return render(request, self.registration_form_template, {'form': form})

    def invite_by_emails(self, emails, sender=None, request=None, **kwargs):
        """Creates an inactive user with the information we know and then sends
        an invitation email for that user to complete registration.
        If your project uses email in a different way then you should make to
        extend this method as it only checks the `email` attribute for Users.
        """
        User = get_user_model()
        users = []
        for email in emails:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create(email=email)
                user.set_password(User.objects.make_random_password())
                user.is_active = False
                user.save()
            self.send_invitation(user, sender, request=request, **kwargs)
            users.append(user)
        return users

    def email_message(self, user, subject_template, body_template, request, sender=None, message_class=EmailMessage, **kwargs):
        """
        Returns an email message for a new user. This can be easily overriden.
        For instance, to send an HTML message, use the EmailMultiAlternatives message_class
        and attach the additional conent.
        """

        if sender:
            import email.utils
            from_email = "%s <%s>" % (
                sender.full_name,
                email.utils.parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
            )
            reply_to = "%s <%s>" % (sender.full_name, sender.email)
        else:
            from_email = settings.DEFAULT_FROM_EMAIL
            reply_to = from_email

        headers = {'Reply-To': reply_to}
        kwargs.update({
            'sender': sender,
            'user': user,
            'accept_url': reverse(
                'aristotle-user:' + self.accept_url_name,
                args=[user.pk, self.get_token(user)]
            ),
            'request': request
        })

        subject_template = loader.get_template(subject_template)
        body_template = loader.get_template(body_template)
        subject = subject_template.render(kwargs).strip()  # Remove stray newline characters
        body = body_template.render(kwargs)
        return message_class(subject, body, from_email, [user.email], headers=headers)

    def send_invitation(self, user, sender=None, **kwargs):
        """An intermediary function for sending an invitation email that
        selects the templates, generating the token, and ensuring that the user
        has not already joined the site.
        """
        if user.is_active:
            return False
        token = self.get_token(user)
        aristotle_settings = fetch_aristotle_settings()
        kwargs.update({
            'token': token,
            'sender': sender,
            'user_id': user.pk,
            'config': aristotle_settings,
        })
        self.email_message(user, self.invitation_subject, self.invitation_body, **kwargs).send()
        return True


class AristotleInvitationBackend(BaseAristotleInvitationBackend):

    # Notification email currently not used
    notification_subject = 'aristotle_mdr/users_management/newuser/email/notification_subject.txt'
    notification_body = 'aristotle_mdr/users_management/newuser/email/notification_body.html'

    invitation_subject = 'aristotle_mdr/users_management/newuser/email/invitation_subject.txt'
    invitation_body = 'aristotle_mdr/users_management/newuser/email/invitation_body.html'
    reminder_subject = 'aristotle_mdr/users_management/newuser/email/reminder_subject.txt'
    reminder_body = 'aristotle_mdr/users_management/newuser/email/reminder_body.html'

    registration_form_template = 'aristotle_mdr/users_management/newuser/register_form.html'


class InviteView(LoginRequiredMixin, PermissionRequiredMixin, FormView):

    form_class = forms.UserInvitationForm
    template_name = "aristotle_mdr/users_management/invite_user_to_registry.html"
    backend = None
    success_url = "aristotle-user:registry_user_list"

    permission_required = "aristotle_mdr.invite_users_to_registry"
    raise_exception = True
    redirect_unauthenticated_users = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            "request": self.request
        })
        return kwargs

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        self.backend.invite_by_emails(form.emails, request=self.request)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.success_url)
