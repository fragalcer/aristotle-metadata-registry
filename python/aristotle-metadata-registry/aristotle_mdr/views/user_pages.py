from typing import List
import datetime
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.generic.edit import FormMixin
from django.views.generic import (
    ListView,
    UpdateView,
    FormView,
    TemplateView,
    View
)

from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.views.utils import (paginated_list,
                                       paginated_workgroup_list,
                                       paginated_registration_authority_list,
                                       GenericListWorkgroup,
                                       AjaxFormMixin)
from aristotle_mdr.views.views import ConceptRenderView, get_app_config_list
from aristotle_mdr.utils import fetch_metadata_apps
from aristotle_mdr.utils import get_aristotle_url
from aristotle_bg_workers.tasks import send_sandbox_notification_emails

import json
import random
import ast

import copy

import logging
logger = logging.getLogger(__name__)


class FriendlyLoginView(LoginView):

    template_name='aristotle_mdr/friendly_login.html'
    redirect_field_name = 'next'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        if self.request.GET.get('welcome', '') == 'true':
            context.update({'welcome': True})

        return context

    def get_redirect_url(self):  # WE HAVE TO OVERRIDE THIS METHOD, TO AVOID A ValueError "Redirection loop for auth..."
        if self.request.GET.get(self.redirect_field_name, '') == reverse("friendly_login"):
            return settings.LOGIN_REDIRECT_URL
        return super().get_redirect_url()


class FriendlyLogoutView(LogoutView):

    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        messages.info(request, _('You have been logged out'))
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, TemplateView):

    template_name='aristotle_mdr/user/userProfile.html'

    def get_user(self):
        return self.request.user

    def get_sessions(self, user):
        return user.session_set.filter(expire_date__gt=datetime.datetime.now())

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        user = self.get_user()
        sessions = self.get_sessions(user)
        context.update({
            # 'user': user,
            'sessions': sessions,
            'session_key': self.request.session.session_key
        })

        return context


@login_required
def home(request):
    from reversion.models import Revision

    recent = Revision.objects.filter(user=request.user).order_by('-date_created')[0:10]
    recentdata = []
    for rev in recent:
        revdata = {'revision': rev, 'versions': []}
        seen_ver_ids = []

        for ver in rev.version_set.all():

            seen = ver.object_id in seen_ver_ids
            add_version = None
            url = None

            if ver.format == 'json':
                object_data = json.loads(ver.serialized_data)

                try:
                    model = object_data[0]['model']
                except KeyError:
                    model = None

                if model:
                    add_version = (model != 'aristotle_mdr.status' and not seen)

                try:
                    name = object_data[0]['fields']['name']
                except KeyError:
                    name = None

                url = get_aristotle_url(object_data[0]['model'], object_data[0]['pk'], name)

            if add_version is None:
                # Fallback for if add_version could not be set, results in db query
                add_version = (not isinstance(ver.object, MDR.Status) and not seen)

            if add_version:

                if url:
                    revdata['versions'].append({'id': ver.object_id, 'text': str(ver), 'url': url})
                else:
                    # Fallback, results in db query
                    try:
                        # If a version exists, but the item has been removed the next line dies
                        obj = ver.object
                        if hasattr(obj, 'get_absolute_url'):
                            revdata['versions'].append({'id': ver.object_id, 'text': str(ver), 'url': obj.get_absolute_url})
                    except:
                        # TODO: Show something properly here
                        pass

            seen_ver_ids.append(ver.object_id)

        if revdata['versions']:
            # Don't append actions where there are no versions to show.
            recentdata.append(revdata)

    recently_viewed = []
    for viewed in (
        request.user.recently_viewed_metadata.all()
        .order_by("-view_date")
        .prefetch_related('concept')[:5]
    ):
        recently_viewed.append(viewed)

    page = render(
        request, "aristotle_mdr/user/userHome.html",
        {
            "item": request.user,
            'recentdata': recentdata,
            "recently_viewed": recently_viewed,
        }
    )
    return page


class Roles(LoginRequiredMixin, TemplateView):

    template_name = 'aristotle_mdr/user/userRoles.html'

    def sort(self, unsorted: List) -> List:
        """Sorts a list by name with secondaty sort on role"""
        # Sort by role (secondary sort)
        sorted_list = sorted(unsorted, key=lambda k: k['role'])
        # Then sort by name (primary sort)
        sorted_list = sorted(sorted_list, key=lambda k: k['name'])
        return sorted_list

    def get_context_data(self):
        user = self.request.user
        workgroups = []
        registration_authorities = []

        for membership in user.workgroupmembership_set.all():
            wg_object = {'name': membership.group.name, 'pk': membership.group.pk, 'role': membership.role}
            workgroups.append(wg_object)

        for ra in user.organization_manager_in.all():
            ra_object = {'name': ra.name, 'pk': ra.pk, 'role': 'Manager'}
            registration_authorities.append(ra_object)

        for ra in user.registrar_in.all():
            ra_object = {'name': ra.name, 'pk': ra.pk, 'role': 'Registrar'}
            registration_authorities.append(ra_object)

        # Ordering
        sorted_workgroups_list = self.sort(workgroups)
        sorted_registration_authorities_list = self.sort(registration_authorities)
        return {
            "user": user,
            "workgroups": sorted_workgroups_list,
            "registration_authorities": sorted_registration_authorities_list
        }


@login_required
def recent(request):
    """ Display the list of the user's recent actions """
    from reversion.models import Revision
    from aristotle_mdr.views.utils import paginated_reversion_list

    items = Revision.objects.filter(user=request.user).order_by('-date_created')
    context = {}

    return paginated_reversion_list(request, items, "aristotle_mdr/user/recent.html", context)


class InboxView(LoginRequiredMixin, ListView):
    template_name = 'aristotle_mdr/user/userInbox.html'
    context_object_name = 'page'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        return self.request.user.notifications.unread().all()

    def get_paginate_by(self, queryset):
        return self.request.GET.get('pp', 25)


class InboxViewAll(LoginRequiredMixin, ListView):
    template_name = 'aristotle_mdr/user/userInbox.html'
    context_object_name = 'page'

    def get_queryset(self, *args, **kwargs):
        return self.request.user.notifications.all()

    def get_paginate_by(self, queryset):
        return self.request.GET.get('pp', 25)


@login_required
def admin_tools(request):
    if request.user.is_anonymous:
        return redirect(reverse('friendly_login') + '?next=%s' % request.path)
    elif not request.user.has_perm("aristotle_mdr.access_aristotle_dashboard"):
        raise PermissionDenied

    aristotle_apps = fetch_metadata_apps()

    from django.contrib.contenttypes.models import ContentType
    models = ContentType.objects.filter(app_label__in=aristotle_apps).all()
    model_stats = {}

    for m in models:
        if m.model_class() and issubclass(m.model_class(), MDR._concept) and not m.model.startswith("_"):
            # Only output subclasses of 11179 concept
            app_models = model_stats.get(m.app_label, {'app': None, 'models': []})
            if app_models['app'] is None:
                app_models['app'] = apps.get_app_config(m.app_label)
            app_models['models'].append(
                (
                    m.model_class(),
                    get_cached_object_count(m),
                    reverse("browse_concepts", args=[m.app_label, m.model])
                )
            )
            model_stats[m.app_label] = app_models

    model_stats = sorted(
        model_stats.values(),
        key=lambda x: (x['app'].create_page_priority, x['app'].create_page_name, x['app'].verbose_name)
    )

    page = render(
        request,
        "aristotle_mdr/user/userAdminTools.html",
        {"item": request.user, "models": model_stats}
    )
    return page


@login_required
def admin_stats(request):
    if request.user.is_anonymous:
        return redirect(reverse('friendly_login') + '?next=%s' % request.path)
    elif not request.user.has_perm("aristotle_mdr.access_aristotle_dashboard"):
        raise PermissionDenied

    aristotle_apps = fetch_metadata_apps()

    from django.contrib.contenttypes.models import ContentType
    models = ContentType.objects.filter(app_label__in=aristotle_apps).all()
    model_stats = {}

    # Get datetime objects for '7 days ago' and '30 days ago'
    t7 = datetime.date.today() - datetime.timedelta(days=7)
    t30 = datetime.date.today() - datetime.timedelta(days=30)
    mod_counts = []  # used to get the maximum count

    use_cache = True  # We still cache but its much, much shorter
    for m in models:
        if m.model_class() and issubclass(m.model_class(), MDR._concept) and not m.model.startswith("_"):
            # Only output subclasses of 11179 concept
            app_models = model_stats.get(m.app_label, {'app': None, 'models': []})
            if app_models['app'] is None:
                app_models['app'] = apps.get_app_config(m.app_label)
            if use_cache:
                total = get_cached_query_count(
                    qs=m.model_class().objects,
                    key=model_to_cache_key(m) + "__all_time",
                    ttl=60
                )
                t7_val = get_cached_query_count(
                    qs=m.model_class().objects.filter(created__gte=t7),
                    key=model_to_cache_key(m) + "__t7",
                    ttl=60
                )
                t30_val = get_cached_query_count(
                    qs=m.model_class().objects.filter(created__gte=t30),
                    key=model_to_cache_key(m) + "__t30",
                    ttl=60
                )
            else:
                total = m.model_class().objects.count()
                t7_val = m.model_class().objects.filter(created__gte=t7).count()
                t30_val = m.model_class().objects.filter(created__gte=t30).count()

            mod_counts.append(total)
            app_models['models'].append(
                (
                    m.model_class(),
                    {
                        'all_time': total,
                        't7': t7_val,
                        't30': t30_val
                    },
                    reverse("browse_concepts", args=[m.app_label, m.model])
                )
            )
            model_stats[m.app_label] = app_models

    model_stats = sorted(
        model_stats.values(),
        key=lambda x: (x['app'].create_page_priority, x['app'].create_page_name, x['app'].verbose_name)
    )

    page = render(
        request, "aristotle_mdr/user/userAdminStats.html",
        {"item": request.user, "model_stats": model_stats, 'model_max': max(mod_counts)}
    )
    return page


def get_cached_query_count(qs, key, ttl):
    count = cache.get(key, None)
    if not count:
        count = qs.count()
        cache.set(key, count, ttl)
    return count


def model_to_cache_key(model_type):
    return 'aristotle_adminpage_object_count_%s_%s' % (model_type.app_label, model_type.model)


def get_cached_object_count(model_type):
    CACHE_KEY = model_to_cache_key(model_type)
    query = model_type.model_class().objects
    return get_cached_query_count(query, CACHE_KEY, 60 * 60 * 12)  # Cache for 12 hours


class EditView(LoginRequiredMixin, UpdateView):
    context_object_name = "object"
    template_name = "aristotle_mdr/user/userEdit.html"
    form_class = MDRForms.EditUserForm

    def get_object(self, querySet=None):
        return copy.deepcopy(self.request.user)

    def get_success_url(self):
        return reverse('aristotle:userProfile')

    def get_initial(self):
        initial = super().get_initial()

        profilepic = self.object.profile.profilePicture

        if profilepic:
            initial.update({
                'profile_picture': profilepic
            })

        return initial

    def form_valid(self, form):

        # Save user object
        self.object = form.save()

        profile = self.object.profile

        picture = form.cleaned_data['profile_picture']
        picture_update = True

        # Determine whether picture has been updated or changed
        if picture:
            if 'profile_picture' in form.changed_data:
                profile.profilePicture = picture
            else:
                picture_update = False
        else:
            profile.profilePicture = None

        # Perform model validation on profile
        if picture_update:
            valid = True
            invalid_message = ''
            try:
                # Resize and format change done on clean
                profile.full_clean()
            except ValidationError as e:
                valid = False
                if 'profilePicture' in e.message_dict:
                    invalid_message = e.message_dict['profilePicture']
                else:
                    invalid_message = e

            if valid:
                profile.save()

            else:
                form.add_error('profile_picture', 'Image could not be saved. {}'.format(invalid_message))
                return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())


class NotificationPermissions(LoginRequiredMixin, FormView):
    form_class = MDRForms.NotificationPermissionsForm
    template_name = 'aristotle_mdr/user/notificationPermissions.html'

    def dispatch(self, request, *args, **kwargs):
        self.profile = request.user.profile
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):

        initial = {
            'notifications_json': json.dumps(self.profile.notificationPermissions)
        }
        return initial

    def form_valid(self, form):
        self.profile.notificationPermissions = form.cleaned_data['notifications_json']
        self.profile.save()
        return HttpResponseRedirect(reverse('aristotle:userProfile'))


class RegistrarTools(LoginRequiredMixin, View):

    template_name = "aristotle_mdr/user/registration_authority/list_all.html"
    model = MDR.RegistrationAuthority

    def get_queryset(self):
        # Return all the ra's a user is a manager of
        manager = Q(managers__pk=self.request.user.pk)
        registrar = Q(registrars__pk=self.request.user.pk)
        visible = Q(active__in=[0, 1])
        return MDR.RegistrationAuthority.objects.filter(visible, manager | registrar)

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        return paginated_registration_authority_list(
            request,
            queryset,
            self.template_name,
            {
                'hide_add_button': True,
                'title_text': 'Your Registration Authorities',
                'activeTab': 'registrarTools'
            }
        )


@login_required
def django_admin_wrapper(request, page_url):
    return render(request, "aristotle_mdr/user/admin.html", {'page_url': page_url})


class SandboxedItemsView(LoginRequiredMixin, AjaxFormMixin, FormMixin, ListView):
    """Display the user's sandbox items"""

    paginate_by = 25
    template_name = "aristotle_mdr/user/sandbox.html"
    form_class = MDRForms.ShareLinkForm
    state_of_emails_before_updating = ""

    def dispatch(self, *args, **kwargs):
        self.share = self.get_share()
        return super().dispatch(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        return self.request.user.profile.mySandboxContent

    def get_share(self):
        if not hasattr(self.request.user, 'profile'):
            return None
        return getattr(self.request.user.profile, 'share', None)

    def get_initial(self):
        initial = super().get_initial()
        share = self.get_share()
        if share is not None:
            emails = json.loads(share.emails)
            initial['emails'] = emails
            self.state_of_emails_before_updating = share.emails

        return initial

    def post(self, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            if not self.request.is_ajax():
                # If request is not ajax and there is an invalid form we need
                # to load the listview content (usually done in get())
                # This should only run if a user has disabled js
                self.object_list = self.get_queryset()
            return self.form_invalid(form)

    def form_valid(self, form):
        emails = form.cleaned_data.get('emails', [])
        emails_json = json.dumps(emails)

        name_of_user = self.request.user.first_name

        if not self.share:
            self.share = MDR.SandboxShare.objects.create(
                profile=self.request.user.profile,
                emails=emails_json
            )

        self.share.emails = emails_json
        self.share.save()
        self.ajax_success_message = 'Share permissions updated'

        if 'notify_new_users_checkbox' in form.cleaned_data and form.cleaned_data.get('notify_new_users_checkbox'):
            # If the notify new users checkbox was selected
            recently_added_emails = self.get_recently_added_emails(
                json.loads(self.state_of_emails_before_updating),
                json.loads(self.share.emails)
            )
            if len(recently_added_emails) > 0:
                # If new emails have been added, send an email
                send_sandbox_notification_emails.delay(
                    name_of_user,
                    recently_added_emails,
                    self.request.get_host() + reverse('aristotle_mdr:sharedSandbox', args=[self.share.uuid])
                )

        return super().form_valid(form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['sort'] = self.request.GET.get('sort', 'name_asc')
        context['share'] = self.share

        if hasattr(self.share, 'emails'):
            context['shared_emails'] = json.loads(self.share.emails)

        if 'form' in kwargs:
            form = kwargs['form']
        else:
            form = self.get_form()

        context['form'] = form
        context['host'] = self.request.get_host()

        if 'display_share' in self.request.GET:
            context['display_share'] = True
            context['number_of_accounts_user_is_sharing_with'] = len(self.get_initial().get('emails'))
        else:
            context['display_share'] = False

        return context

    def get_ordering(self):
        from aristotle_mdr.views.utils import paginate_sort_opts
        self.order = self.request.GET.get('sort', 'name_asc')
        return paginate_sort_opts.get(self.order)

    def get_success_url(self):
        return reverse('aristotle_mdr:userSandbox') + '?display_share=1'

    def get_recently_added_emails(self, old_emails, new_emails):
        return list(set(new_emails) - set(old_emails))


class GetShareMixin:
    """Code shared by all share link views"""

    def dispatch(self, request, *args, **kwargs):
        self.share = self.get_share_obj()
        emails = json.loads(self.share.emails)

        not_in_shared_emails = request.user.email not in emails
        not_own_sandbox = request.user.id != self.share.profile.user_id

        if not_in_shared_emails and not_own_sandbox:
            # If the user is not in the list of allowed emails or it's not their own sandbox
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_share_obj(self):
        uuid = self.kwargs['share']
        try:
            share = MDR.SandboxShare.objects.get(uuid=uuid)
        except MDR.SandboxShare.DoesNotExist:
            share = None

        return share


class SharedSandboxView(LoginRequiredMixin, GetShareMixin, ListView):
    """View displayed when a user visits a share link"""

    paginate_by = 25
    template_name = 'aristotle_mdr/user/shared_sandbox.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['share_user'] = self.share.profile.user
        context['share_uuid'] = self.share.uuid

        # Display all metadata links though share
        context['shared_items'] = True
        return context

    def get_queryset(self, *args, **kwargs):
        return self.share.profile.mySandboxContent


class SharedItemView(LoginRequiredMixin, GetShareMixin, ConceptRenderView):
    """View to display an item in a shared sandbox"""

    slug_redirect = False

    def check_item(self, item):
        self.sandbox_ids = list(self.user.profile.mySandboxContent.values_list('id', flat=True))
        if item.id in self.sandbox_ids:
            return True
        else:
            return False

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['hide_item_actions'] = True
        context['hide_item_tabs'] = True
        context['custom_visibility_message'] = {
            'alert_level': 'warning',
            'message': 'You are viewing a shared item in read only mode'
        }

        share_user = self.share.profile.user
        user_display_name = share_user.full_name or share_user.short_name or share_user.email
        context['breadcrumbs'] = [
            {
                'name': '{}\'s Sandbox'.format(user_display_name),
                'url': reverse('aristotle:sharedSandbox', args=[self.share.uuid])
            },
            {
                'name': self.item.name,
                'active': True
            }
        ]
        # Set these in order to display links to other sandbox content  correctly
        context['shared_ids'] = self.sandbox_ids
        context['share_uuid'] = self.share.uuid
        return context

    def get_user(self):
        return self.share.profile.user


class MyWorkgroupList(GenericListWorkgroup):
    template_name = "aristotle_mdr/user/userWorkgroups.html"

    def get_initial_queryset(self):
        return self.request.user.profile.myWorkgroups


class WorkgroupArchiveList(GenericListWorkgroup):
    template_name = "aristotle_mdr/user/userWorkgroupArchives.html"

    def get_initial_queryset(self):
        user = self.request.user
        return user.profile.workgroups_for_user().filter(archived=True)


def profile_picture(request, uid):
    from django.contrib.auth import get_user_model
    user = get_object_or_404(get_user_model(), pk=uid)
    if user.profile.profilePicture:
        return HttpResponse(user.profile.profilePicture.read(), content_type="image/png")

    template_name = 'aristotle_mdr/user/user-head.svg'

    # Seed with user id
    random.seed(uid)

    colors = []
    for i in range(2):
        colors.append('#{0:X}'.format(random.randint(0, 0xFFFFFF)))

    context = {
        'toga_color': colors[0],
        'headshot_color': colors[1]
    }

    return render(
        request,
        template_name,
        context=context,
        content_type='image/svg+xml'
    )
