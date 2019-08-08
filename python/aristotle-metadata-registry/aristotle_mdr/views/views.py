from typing import Any
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.exceptions import PermissionDenied, FieldDoesNotExist, ObjectDoesNotExist
from django.urls import reverse
from django.db import transaction
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView, RedirectView, DeleteView, UpdateView
from django.utils.module_loading import import_string
from django.utils.functional import SimpleLazyObject
from django.utils import timezone
from formtools.wizard.views import SessionWizardView

import json

import reversion

from aristotle_mdr.perms import (
    user_can_view, user_can_edit,
    user_can_add_status,
    user_can_publish_object,
    user_can_supersede,
    user_can_add_status
)
from aristotle_mdr import perms
from aristotle_mdr.utils import url_slugify_concept
from aristotle_mdr.forms import EditStatusForm
from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.utils import (
    cascade_items_queryset,
    get_concepts_for_apps,
    fetch_aristotle_settings,
    fetch_aristotle_downloaders,
    fetch_metadata_apps
)
from aristotle_mdr.views.utils import (
    generate_visibility_matrix,
    CachePerItemUserMixin,
    TagsMixin
)
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.contrib.custom_fields.models import CustomField, CustomValue
from aristotle_mdr.contrib.links.utils import get_all_links_for_concept
from aristotle_bg_workers.tasks import register_items
from aristotle_bg_workers.utils import run_task_on_commit

from reversion.models import Version


import logging

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)

PAGES_PER_RELATED_ITEM = 15


class SmartRoot(RedirectView):
    unauthenticated_pattern = None
    authenticated_pattern = None

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated():
            self.pattern_name = self.authenticated_pattern
        else:
            self.pattern_name = self.unauthenticated_pattern
        return super().get_redirect_url(*args, **kwargs)


class DynamicTemplateView(TemplateView):
    def get_template_names(self):
        return ['aristotle_mdr/static/%s.html' % self.kwargs['template']]


def notification_redirect(self, content_type, object_id):

    ct = ContentType.objects.get(id=content_type)
    model_class = ct.model_class()
    obj = model_class.objects.get(id=object_id)
    return HttpResponseRedirect(obj.get_absolute_url())


def get_if_user_can_view(objtype, user, iid):
    item = get_object_or_404(objtype, pk=iid)
    if user_can_view(user, item):
        return item
    else:
        return False


def concept_by_uuid(request, uuid):
    item = get_object_or_404(MDR._concept, uuid=uuid)
    return redirect(url_slugify_concept(item))


def measure(request, iid, model_slug, name_slug):
    return managed_item(request, "measure", iid)


# TODO: Switch to CBV
def managed_item(request, model_slug, iid):
    model_class = get_object_or_404(ContentType, model=model_slug).model_class()
    item = get_object_or_404(model_class, pk=iid).item

    if not user_can_view(request.user, item):
        raise PermissionDenied

    return render(
        request, [getattr(item, 'template', "aristotle_mdr/manageditems/fallback.html")],
        {
            'item': item,
            'group': item.stewardship_organisation,
            'model_name': item.meta().model_name,
            "activetab": "item",
        }
    )


class ConceptRenderView(TagsMixin, TemplateView):
    """
    Class based view for rendering a concept, replaces render_if_condition_met

    **This should be used with a permission mixin or check_item override**
    slug_redirect determines whether /item/id redirects to /item/id/model_slug/name_slug
    """

    objtype: Any = None
    itemid_arg: str = 'iid'
    modelslug_arg: str = 'model_slug'
    nameslug_arg: str = 'name_slug'
    slug_redirect: bool = False

    def get_queryset(self, concept):
        ct = concept.item_type
        model = ct.model_class()
        return self.get_related(model)

    def get_item(self):
        # Get itemid from kwargs
        itemid = self.kwargs[self.itemid_arg]
        # Lookup concept
        concept = get_object_or_404(MDR._concept, pk=itemid)
        # Get queryset with (with select/prefetchs)
        queryset = self.get_queryset(concept)
        # Fetch subclassed item
        try:
            item = queryset.get(pk=itemid)
        except ObjectDoesNotExist:
            item = None
        return item

    def get_related(self, model):
        """Returns a queryset fetching related concepts"""
        related_fields = []
        prefetch_fields = ['statuses']
        for field in model._meta.get_fields():
            # Get select related fields
            if model.related_objects:
                related_fields = model.related_objects
            else:
                if field.is_relation and field.many_to_one and issubclass(field.related_model, MDR._concept):
                    # If a field is a foreign key that links to a concept
                    related_fields.append(field.name)

            # Get prefetch related fields
            if field.is_relation and field.one_to_many and issubclass(field.related_model, MDR.AbstractValue):
                # If field is a reverse foreign key that links to an
                # abstract value
                prefetch_fields.append(field.name)

        return model.objects.select_related(*related_fields).prefetch_related(*prefetch_fields)

    def check_item(self, item):
        # To be overwritten
        # Fail safely
        return False

    def check_app(self, item):
        label = type(item)._meta.app_label
        if label not in fetch_metadata_apps():
            return False
        return True

    def get_user(self):
        return self.request.user

    def get_redirect(self):
        if not self.modelslug_arg:
            model_correct = True
        else:
            model_slug = self.kwargs.get(self.modelslug_arg, '')
            model_correct = (self.item._meta.model_name == model_slug)

        name_slug = self.kwargs.get(self.nameslug_arg, '')
        # name_correct = (slugify(self.item.name) == name_slug)
        name_present = (name_slug is not None)

        if not model_correct or not name_present:
            return True, url_slugify_concept(self.item)
        else:
            return False, ''

    def dispatch(self, request, *args, **kwargs):
        self.item = self.get_item()

        if self.item is None:
            # If item was not found and no redirect was needed
            raise Http404

        if self.slug_redirect:
            redirect, url = self.get_redirect()
            if redirect:
                return HttpResponseRedirect(url)

        self.user = self.get_user()

        app_enabled = self.check_app(self.item)
        if not app_enabled:
            raise Http404

        result = self.check_item(self.item)
        if not result:
            if self.request.user.is_anonymous():
                redirect_url = '{}?next={}'.format(
                    reverse('friendly_login'),
                    self.request.path
                )
                return HttpResponseRedirect(redirect_url)
            else:
                raise PermissionDenied

        from aristotle_mdr.contrib.view_history.signals import metadata_item_viewed
        metadata_item_viewed.send(sender=self.item, user=self.user.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_links(self):
        from_links = []
        to_links = []

        for l in get_all_links_for_concept(self.item):
            if l.root_item_id == self.item.pk:
                from_links.append(l)
            else:
                to_links.append(l)

        return (from_links, to_links)

    def get_custom_values(self):
        allowed = CustomField.objects.get_allowed_fields(self.item.concept, self.request.user)
        custom_values = CustomValue.objects.get_allowed_for_item(self.item.concept, allowed)
        not_empty_custom_values = []
        for value in custom_values:
            if value.content:
                not_empty_custom_values.append(value)
        return not_empty_custom_values

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        if self.request.user.is_anonymous():
            context['isFavourite'] = False
        else:
            context['isFavourite'] = self.request.user.profile.is_favourite(self.item)

        aristotle_settings = fetch_aristotle_settings()

        links_from, links_to = self.get_links()

        context.update({
            'last_edit': Version.objects.get_for_object(self.item).first(),
            # Only display viewable slots
            'slots': Slot.objects.get_item_allowed(self.item, self.user),
            'item': self.item,
            'statuses': self.item.current_statuses,
            'discussions': self.item.relatedDiscussions.all(),
            'activetab': 'item',
            'has_links': links_from or links_to,
            'links_from': links_from,
            'links_to': links_to,
            'custom_values': self.get_custom_values(),
            'submitting_organizations': self.item.submitting_organizations,
            'responsible_organizations': self.item.responsible_organizations,
            'infobox_identifier_name': aristotle_settings['INFOBOX_IDENTIFIER_NAME']
        })

        # Add a list of viewable concept ids for fast visibility checks in
        # templates
        # Since its lazy we can do this everytime :)
        lazy_viewable_ids = SimpleLazyObject(
            lambda: list(MDR._concept.objects.visible(self.user).values_list('id', flat=True))
        )
        context['viewable_ids'] = lazy_viewable_ids

        # Permissions (so they are looked up once)
        context.update({
            'can_edit': user_can_edit(self.user, self.item),
            'can_publish': user_can_publish_object(self.user, self.item),
            'can_supersede': user_can_supersede(self.user, self.item),
            'can_add_status': user_can_add_status(self.user, self.item)
        })

        return context

    def get_template_names(self):
        default_template = "{}/concepts/{}.html".format(
            self.item.__class__._meta.app_label,
            self.item.__class__._meta.model_name
        )

        return [default_template, self.item.template]


# General concept view
class ConceptView(ConceptRenderView):

    slug_redirect = True
    cache_item_kwarg = 'iid'
    cache_view_name = 'ConceptView'

    def check_item(self, item):
        return user_can_view(self.request.user, item)


class ObjectClassView(ConceptRenderView):

    objtype = MDR.ObjectClass

    def check_item(self, item):
        return user_can_view(self.request.user, item)

    def get_related(self, model):
        related_objects = [
        ]
        prefetch_objects = [
            'statuses'
        ]
        return model.objects.prefetch_related(*prefetch_objects)


class DataElementView(ConceptRenderView):

    objtype = MDR.DataElement

    def check_item(self, item):
        return user_can_view(self.request.user, item)

    def get_related(self, model):
        related_objects = [
            'valueDomain',
            'dataElementConcept__objectClass',
            'dataElementConcept__property'
        ]
        prefetch_objects = [
            'valueDomain__permissiblevalue_set',
            'valueDomain__supplementaryvalue_set',
            'statuses'
        ]
        return model.objects.select_related(*related_objects).prefetch_related(*prefetch_objects)


def registrationHistory(request, iid):
    item = get_if_user_can_view(MDR._concept, request.user, iid)
    if not item:
        if request.user.is_anonymous():
            return redirect(reverse('friendly_login') + '?next=%s' % request.path)
        else:
            raise PermissionDenied

    history = item.statuses.order_by("registrationAuthority", "-effective_date", "-until_date", "-created")
    out = {}
    for status in history:
        if status.registrationAuthority in out.keys():
            out[status.registrationAuthority].append(status)
        else:
            out[status.registrationAuthority] = [status]

    return render(request, "aristotle_mdr/registrationHistory.html", {'item': item, 'history': out})


def unauthorised(request, path=''):
    if request.user.is_anonymous():
        return render(request, "401.html", {"path": path, "anon": True, }, status=401)
    else:
        return render(request, "403.html", {"path": path, "anon": True, }, status=403)


def not_found(request, path):
    context = {'anon': request.user.is_anonymous(), 'path': path}
    return render(request, "404.html", context)


def handler500(request, *args, **argv):
    return render(request, '500.html')


def create_list(request):
    if request.user.is_anonymous():
        return redirect(reverse('friendly_login') + '?next=%s' % request.path)
    if not perms.user_is_editor(request.user):
        raise PermissionDenied

    aristotle_apps = fetch_aristotle_settings().get('CONTENT_EXTENSIONS', [])
    aristotle_apps += ["aristotle_mdr"]
    out = {}

    wizards = []
    for wiz in getattr(settings, 'ARISTOTLE_SETTINGS', {}).get('METADATA_CREATION_WIZARDS', []):
        w = wiz.copy()
        _w = {
            'model': apps.get_app_config(wiz['app_label']).get_model(wiz['model']),
            'class': import_string(wiz['class']),
        }
        w.update(_w)
        wizards.append(w)

    return render(
        request, "aristotle_mdr/create/create_list.html",
        {
            'models': get_app_config_list(),
            'wizards': wizards
        }
    )


def get_app_config_list(count=False):
    out = {}
    aristotle_apps = fetch_metadata_apps()

    for m in get_concepts_for_apps(aristotle_apps):
        # Only output subclasses of 11179 concept
        app_models = out.get(m.app_label, {'app': None, 'models': []})

        if app_models['app'] is None:
            try:
                app_models['app'] = apps.get_app_config(m.app_label)
            except:
                # Where no name is configured in the app_config, set a dummy so we don't keep trying
                from aristotle_mdr.apps import AristotleExtensionBaseConfig
                app = AristotleExtensionBaseConfig()
                app.verbose_name = "No name"
                app_models['app'] = app
        app_models['models'].append({
            "content_type": m,
            "class": m.model_class()
        })
        out[m.app_label] = app_models

    return sorted(
        out.values(),
        key=lambda x: (x['app'].create_page_priority, x['app'].create_page_name, x['app'].verbose_name)
    )


def display_review(wizard):
    if wizard.display_review is not None:
        return wizard.display_review
    else:
        return True


class ReviewChangesView(SessionWizardView):
    """Abstract view used by registration views"""

    items: Any = None
    display_review: Any = None

    # Override this
    change_step_name = ''

    def get_items(self):
        raise NotImplementedError

    def get_form_kwargs(self, step):

        if step == 'review_changes':
            items = self.get_items()
            # Check some values from last step
            cleaned_data = self.get_change_data()
            cascade = cleaned_data['cascadeRegistration']
            state = cleaned_data['state']
            ra = cleaned_data['registrationAuthorities']

            static_content = {'new_state': state, 'new_reg_date': cleaned_data['effective_date']}
            # Need to check wether cascaded was true here

            if cascade == 1:
                queryset = cascade_items_queryset(items=items)
            else:
                ids = [a.id for a in items]
                queryset = MDR._concept.objects.filter(id__in=ids)

            return {'queryset': queryset, 'static_content': static_content, 'ra': ra[0], 'user': self.request.user}

        return {}

    def get_form(self, step=None, data=None, files=None):

        self.set_review_var(step, data, files, self.change_step_name)
        return super().get_form(step, data, files)

    def get_change_data(self):
        # We override this when the change_data doesnt come form a form
        return self.get_cleaned_data_for_step(self.change_step_name)

    def set_review_var(self, step, data, files, change_step):

        # Set step if it's None
        if step is None:
            step = self.steps.current

        if step == change_step and data:
            review = True
            if data.get('submit_next'):
                review = True
            elif data.get('submit_skip'):
                review = False

            self.display_review = review

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)

        if self.steps.current == 'review_changes':
            data = self.get_cleaned_data_for_step(self.change_step_name)
            if 'registrationAuthorities' in data:
                context.update({'ra': data['registrationAuthorities'][0]})

        return context

    def register_changes(self, form_dict, change_form=None, **kwargs):

        can_cascade = True
        items = self.get_items()

        try:
            review_data = form_dict['review_changes'].cleaned_data
        except KeyError:
            review_data = None

        # If user went through to review changes form
        if review_data:
            selected_list = review_data['selected_list']
            # Set items based on user selected items
            items = selected_list
            # Make sure we dont cascade when items were specifically selected
            can_cascade = False

        # Get ids of items
        if isinstance(items, QuerySet):
            item_ids = list(items.values_list('id', flat=True))
        else:
            item_ids = [i.id for i in items]

        # process the data in form.cleaned_data as required
        if change_form:
            cleaned_data = form_dict[change_form].cleaned_data
        else:
            cleaned_data = self.get_change_data(register=True)

        ras = cleaned_data['registrationAuthorities']
        state = cleaned_data['state']
        regDate = cleaned_data['effective_date']
        cascade = cleaned_data['cascadeRegistration']
        changeDetails = cleaned_data['changeDetails']

        if changeDetails is None:
            changeDetails = ""

        if not regDate:
            regDate = timezone.now().date()

        cascading = (can_cascade and cascade)

        # Register items (using celery if required)
        register_args = [
            item_ids,
            cascading,
            state,
            ras[0].id,
            self.request.user.id,
            changeDetails,
            (regDate.year, regDate.month, regDate.day)
        ]

        use_celery: bool = (len(item_ids) > 1 or cascading)
        if settings.ALWAYS_SYNC_REGISTER:
            use_celery = False

        if use_celery:
            run_task_on_commit(register_items, args=register_args)
        else:
            register_items(*register_args)


class ChangeStatusView(ReviewChangesView):

    change_step_name = 'change_status'

    form_list = [
        ('change_status', MDRForms.ChangeStatusForm),
        ('review_changes', MDRForms.ReviewChangesForm)
    ]

    templates = {
        'change_status': 'aristotle_mdr/actions/changeStatus.html',
        'review_changes': 'aristotle_mdr/actions/review_state_changes.html'
    }

    condition_dict = {'review_changes': display_review}

    display_review = None

    def dispatch(self, request, *args, **kwargs):
        # Check for keyError here
        self.item = get_object_or_404(MDR._concept, pk=kwargs['iid']).item

        if not user_can_add_status(request.user, self.item):
            if request.user.is_anonymous():
                return redirect(reverse('friendly_login') + '?next=%s' % request.path)
            else:
                raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_items(self):
        return [self.item]

    def get_form_kwargs(self, step):

        kwargs = super().get_form_kwargs(step)

        if step == 'change_status':
            return {'user': self.request.user}

        return kwargs

    def get_context_data(self, form, **kwargs):
        item = self.item
        status_matrix = json.dumps(generate_visibility_matrix(self.request.user))
        context = super().get_context_data(form, **kwargs)
        context.update({'item': item, 'status_matrix': status_matrix})
        return context

    def done(self, form_list, form_dict, **kwargs):
        self.register_changes(form_dict, 'change_status')
        return HttpResponseRedirect(url_slugify_concept(self.item))


class DeleteStatus(DeleteView):

    model = MDR.Status

    def get_object(self, queryset=None):
        return get_object_or_404(MDR.Status, pk=self.kwargs['sid'])

    def delete(self, request, *args, **kwargs):

        status_to_be_deleted = self.get_object()
        status_to_be_deleted.delete()

        # Update the search engine indexation for the concept:
        from aristotle_mdr.models import concept_visibility_updated
        item_to_be_updated = get_object_or_404(MDR._concept, pk=self.kwargs['iid'])
        concept_visibility_updated.send(concept=item_to_be_updated, sender=self.__class__)
        return HttpResponseRedirect(reverse('aristotle:registrationHistory', kwargs={'iid': self.kwargs['iid']}))


class EditStatus(UpdateView):
    template_name = 'aristotle_mdr/status_edit.html'
    form_class = EditStatusForm
    model = MDR.Status

    def get_object(self, queryset=None):
        return get_object_or_404(MDR.Status, pk=self.kwargs['sid'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update({'ra': self.RA, 'item': self.item})

        return context

    def get_initial(self):
        self.RA = get_object_or_404(MDR.RegistrationAuthority, pk=self.kwargs['raid'])
        self.item = get_object_or_404(MDR._concept, pk=self.kwargs['iid'])
        self.status = get_object_or_404(MDR.Status, pk=self.kwargs['sid'])
        initial = super().get_initial()
        initial['effective_date'] = self.status.effective_date
        initial['until_date'] = self.status.until_date
        initial['state'] = self.status.state

        return initial

    def form_valid(self, form):
        self.object = form.save()
        # Update the search engine indexation for the concept:
        from aristotle_mdr.models import concept_visibility_updated
        concept_visibility_updated.send(concept=self.get_object().concept, sender=self.get_object().concept.__class__)
        return redirect(reverse('aristotle:registrationHistory', args=[self.kwargs['iid']]))


def extensions(request):
    content = []
    aristotle_apps = fetch_aristotle_settings().get('CONTENT_EXTENSIONS', [])

    if aristotle_apps:
        for app_label in aristotle_apps:
            app=apps.get_app_config(app_label)
            try:
                app.about_url = reverse('%s:about' % app_label)
            except:
                pass  # if there is no about URL, thats ok.
            content.append(app)

    content = list(set(content))
    aristotle_downloaders = fetch_aristotle_downloaders()
    download_extensions = [dler.get_class_info() for dler in aristotle_downloaders]

    return render(
        request,
        "aristotle_mdr/static/extensions.html",
        {'content_extensions': content, 'download_extensions': download_extensions}
    )
