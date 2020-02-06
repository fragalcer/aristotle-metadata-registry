from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.urls import reverse
from django.views.generic import ListView, TemplateView
from django.db.models.functions import Substr, Upper

from aristotle_mdr.utils import fetch_metadata_apps, cloud_enabled
from aristotle_mdr.models import _concept
from aristotle_mdr.views.views import get_app_config_list

import logging
logger = logging.getLogger(__name__)


def add_urls_to_config_list(config_list):
    """Util function to add URLs to the *config_list* queryset"""
    for app in config_list:
        for model in app['models']:
            model['url'] = reverse('browse_concepts',
                                   args=[model['content_type'].app_label, model['content_type'].model])
        app['url'] = reverse('browse_models', args=[app['app'].label])
    return config_list


class BrowseStartView(TemplateView):
    """A starting view for Browse that serves as a central jumping off point for the other views"""
    template_name = 'aristotle_mdr_browse/main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['aristotle_cloud_is_active'] = cloud_enabled()
        return context


class BrowseAppsView(TemplateView):
    """Main browse page listing all the apps to browse"""
    template_name = "aristotle_mdr_browse/apps_list.html"
    ordering = 'app_label'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['apps'] = add_urls_to_config_list(get_app_config_list())
        context['browse_all_metadata_url'] = ""
        return context


class AppBrowser(ListView):
    """ListView with some extra context (subclassed by following views)"""

    def get_app_label(self):
        return self.kwargs['app']

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        app = self.get_app_label()
        if app not in fetch_metadata_apps():
            raise Http404
        context['app_label'] = app
        context['app'] = apps.get_app_config(app)
        return context


class BrowseModelsView(AppBrowser):
    template_name = "aristotle_mdr_browse/model_list.html"
    context_object_name = "model_list"
    paginate_by = 25

    def get_queryset(self):
        app = self.get_app_label()
        if app not in fetch_metadata_apps():
            raise Http404
        app_config = get_app_config_list([app])

        return add_urls_to_config_list(app_config)


def annotate_with_first_letter(qs):
    """A function to annotate the queryset with the first letter of the concept's name. (Currently unused)"""
    return qs.annotate(first_letter=Upper(Substr('name', 1, 1)))


class BrowseConceptsView(AppBrowser):
    """Show a list of items of a particular model"""
    _model = None
    paginate_by = 25

    def get_model_name(self):
        return self.kwargs['model']

    @property
    def model(self):
        if self.get_app_label() not in fetch_metadata_apps():
            logger.critical(self.get_app_label())
            raise Http404
        if self._model is None:
            app = self.get_app_label()
            model = self.get_model_name()
            ct = ContentType.objects.filter(app_label=app, model=model)
            if not ct:
                raise Http404
            else:
                self._model = ct.first().model_class()
        if not issubclass(self._model, _concept):
            raise Http404
        return self._model

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset(*args, **kwargs)
        return queryset.visible(self.request.user).prefetch_related('statuses__registrationAuthority')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['model'] = self.model
        context['model_name'] = self.model._meta.model_name
        context['sort'] = self.order
        context['total_queryset_size'] = self.get_queryset().count()
        return context

    def get_template_names(self):
        app_label = self.kwargs['app']
        names = super().get_template_names()
        names.append('aristotle_mdr_browse/list.html')
        names.insert(0, 'aristotle_mdr_browse/%s/%s_list.html' % (app_label, self.model._meta.model_name))
        return names

    def get_ordering(self):
        from aristotle_mdr.views.utils import paginate_sort_opts
        self.order = self.request.GET.get('sort', 'name_asc')
        return paginate_sort_opts.get(self.order)


class BrowseAllMetadataView(BrowseConceptsView):
    def get_model_name(self):
        return '_concept'

    def get_app_label(self):
        return 'aristotle_mdr'
