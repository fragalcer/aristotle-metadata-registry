import datetime
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db.models import Q, Count
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic.edit import FormMixin
from django.views.generic import (DetailView,
                                  ListView,
                                  UpdateView,
                                  FormView,
                                  TemplateView,
                                  View)

from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.views.utils import (paginated_list,
                                       paginated_workgroup_list,
                                       paginated_registration_authority_list,
                                       GenericListWorkgroup,
                                       AjaxFormMixin)
from aristotle_mdr.views.views import ConceptRenderView
from aristotle_mdr.utils import fetch_metadata_apps
from aristotle_mdr.utils import get_aristotle_url

import json
import random


class FriendlyLoginView(LoginView):

    template_name='aristotle_mdr/friendly_login.html'
    redirect_field_name = 'next'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        if self.request.GET.get('welcome', '') == 'true':
            context.update({'welcome': True})

        return context


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
                    # print(ver)
                    obj = ver.object
                    if hasattr(obj, 'get_absolute_url'):
                        revdata['versions'].append({'id': ver.object_id, 'text': str(ver), 'url': obj.get_absolute_url})

            seen_ver_ids.append(ver.object_id)

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


@login_required
def roles(request):
    page = render(request, "aristotle_mdr/user/userRoles.html", {"item": request.user})
    return page


@login_required
def recent(request):
    from reversion.models import Revision
    from aristotle_mdr.views.utils import paginated_reversion_list
    items = Revision.objects.filter(user=request.user).order_by('-date_created')
    context = {}
    return paginated_reversion_list(request, items, "aristotle_mdr/user/recent.html", context)


@login_required
def inbox(request, folder=None):
    if folder is None:
        # By default show only unread
        folder='unread'
    folder=folder.lower()
    if folder == 'unread':
        notices = request.user.notifications.unread().all()
    elif folder == "all":
        notices = request.user.notifications.all()
    page = render(
        request,
        "aristotle_mdr/user/userInbox.html",
        {"item": request.user, "notifications": notices, 'folder': folder}
    )
    return page


@login_required
def admin_tools(request):
    if request.user.is_anonymous():
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
                app_models['app'] = getattr(apps.get_app_config(m.app_label), 'verbose_name')
            app_models['models'].append(
                (
                    m.model_class(),
                    get_cached_object_count(m),
                    reverse("browse_concepts", args=[m.app_label, m.model])
                )
            )
            model_stats[m.app_label] = app_models

    page = render(
        request,
        "aristotle_mdr/user/userAdminTools.html",
        {"item": request.user, "models": model_stats}
    )
    return page


@login_required
def admin_stats(request):
    if request.user.is_anonymous():
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
                app_models['app'] = getattr(apps.get_app_config(m.app_label), 'verbose_name')
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
        return self.request.user

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


# @login_required
# def my_review_list(request):
#     # Users can see any items they have been asked to review
#     q = Q(requester=request.user)
#     reviews = MDR.ReviewRequest.objects.visible(request.user).filter(q).filter(registration_authority__active=0)
#     return paginated_list(request, reviews, "aristotle_mdr/user/my_review_list.html", {'reviews': reviews})


@login_required
def django_admin_wrapper(request, page_url):
    return render(request, "aristotle_mdr/user/admin.html", {'page_url': page_url})


class CreatedItemsListView(LoginRequiredMixin, AjaxFormMixin, FormMixin, ListView):
    """Display Users sandbox items"""

    paginate_by = 25
    template_name = "aristotle_mdr/user/sandbox.html"
    form_class = MDRForms.ShareLinkForm

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

        return initial

    def get_context_data(self, *args, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(*args, **kwargs)
        context['sort'] = self.request.GET.get('sort', 'name_asc')
        context['share'] = self.share

        if 'form' in kwargs:
            form = kwargs['form']
        else:
            form = self.get_form()

        context['form'] = form
        context['host'] = self.request.get_host()
        context['number_of_accounts_user_is_sharing_with'] = len(self.get_initial().get('emails'))

        return context

    def post(self, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            if not self.request.is_ajax():
                # If request is not ajax and there is an invlaid form we need
                # to load the listview content (usually done in get())
                # This should only run if a user has disabled js
                self.object_list = self.get_queryset()
            return self.form_invalid(form)

    def form_valid(self, form):

        emails = form.cleaned_data.get('emails', [])
        emails_json = json.dumps(emails)

        if not self.share:
            MDR.SandboxShare.objects.create(
                profile=self.request.user.profile,
                emails=emails_json
            )
        else:
            self.share.emails = emails_json
            self.share.save()
            self.ajax_success_message = 'Share permissions updated'

        return super().form_valid(form)

    def get_ordering(self):
        from aristotle_mdr.views.utils import paginate_sort_opts
        self.order = self.request.GET.get('sort', 'name_asc')
        return paginate_sort_opts.get(self.order)

    def get_success_url(self):
        return reverse('aristotle_mdr:userSandbox')


class GetShareMixin:
    """Code shared by all share link views"""

    def dispatch(self, request, *args, **kwargs):
        self.share = self.get_share()
        emails = json.loads(self.share.emails)
        if request.user.email not in emails:
            return HttpResponseNotFound()
        return super().dispatch(request, *args, **kwargs)

    def get_share(self):
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

        # Set these in order to display links to other sandbox content
        # correctly
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
        return (
            user.viewer_in.all() |
            user.submitter_in.all() |
            user.steward_in.all() |
            user.workgroup_manager_in.all()
        ).filter(archived=True).distinct()


def profile_picture(request, uid):

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
