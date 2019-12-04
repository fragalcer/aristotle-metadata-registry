from typing import List, Dict, Any, Iterable
from django.urls import reverse
from django.http import (
    Http404,
)
from django.views.generic import TemplateView, View, FormView
from django.core.files.storage import get_storage_class

from aristotle_mdr import models as MDR
from aristotle_mdr.utils.download import get_download_class
from aristotle_bg_workers.tasks import download
from celery.result import AsyncResult as async_result
from aristotle_mdr.forms.downloads import DownloadOptionsForm

import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)

PAGES_PER_RELATED_ITEM = 15


class BaseDownloadView(TemplateView):
    """
    Base class inherited by single and bulk download views below
    """
    template_name = 'aristotle_mdr/downloads/creating_download.html'
    bulk = False

    options_session_key = 'download_options'

    def get_item_id_list(self) -> List[int]:
        """Returns a list of item ids"""
        raise NotImplementedError

    def get(self, request, *args, **kwargs):
        download_type = self.kwargs['download_type']
        self.item_ids = self.get_item_id_list()

        if request.user.is_authenticated:
            user_id = request.user.id
        else:
            user_id = None

        if self.options_session_key in request.session:
            options = request.session[self.options_session_key]
        else:
            # Default option on the downloader class will be used
            options = {}

        downloader_class = get_download_class(download_type)

        if not downloader_class:
            raise Http404

        # Add the current host url to the options to make the relative links clickable:
        options.update({"CURRENT_HOST": request.scheme + "://" +request.get_host()})

        res = download.delay(download_type, self.item_ids, user_id, options)

        request.session['download_result_id'] = res.id
        # res.forget()
        self.download_type = download_type
        self.download_class = downloader_class
        self.taskid = res.id
        return super().get(request, *args, **kwargs)

    def get_item_names(self) -> Iterable[str]:
        name_list = MDR._concept.objects.filter(id__in=self.item_ids).values_list('name', flat=True)
        return name_list

    def get_file_title(self, item_names: Iterable[str]) -> str:
        return 'Item Download'

    def get_file_details(self) -> Dict[str, Any]:
        item_names = self.get_item_names()
        details = {
            'title': self.get_file_title(item_names),
            'items': ', '.join(item_names),
            'is_bulk': len(self.item_ids) > 1,
        }
        details.update(self.download_class.get_class_info())
        return details

    def get_context_data(self, *args, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(*args, **kwargs)

        context.update({
            'items': self.item_ids,
            'file_details': self.get_file_details(),
            'task_id': self.taskid
        })
        return context


class DownloadView(BaseDownloadView):

    def get_item_id_list(self):
        iid = int(self.kwargs['iid'])
        item_ids = [iid]
        return item_ids

    def get_file_title(self, item_names):
        return item_names[0] + ' Download'


class BulkDownloadView(BaseDownloadView):

    def get_item_id_list(self):
        from aristotle_mdr.utils.cached_querysets import get_queryset_from_uuid
        id_strings = self.request.GET.getlist('items')
        qs_uuid = self.request.GET.get('qs')

        if qs_uuid:
            try:
                qs = get_queryset_from_uuid(qs_uuid)
                ids = list(qs.values_list('id', flat=True))
            except ValueError:
                raise Http404("Queryset not found")
        else:
            try:
                ids = [int(id) for id in id_strings]
            except ValueError:
                raise Http404

        return ids

    def get_file_title(self, item_names):
        return 'Bulk Download'


class DownloadStatusView(View):
    """
    This view lets user know that the download is being prepared.
    Checks:
    1. check if there is a celery task id present in the session.
    2. check if the celery task id expired/already downloaded.
    3. check if the job is ready.
    :param request: request object from the API call.
    :param download_type: type of download
    :return: appropriate HTTP response object
    """

    download_key = 'download_result_id'

    def get(self, request, *args, **kwargs):
        if 'taskid' not in self.kwargs:
            raise Http404

        task_id = self.kwargs['taskid']

        # Check if the job exists
        job = async_result(task_id)
        context = {
            'is_ready': False,
            'is_expired': False,
            'state': job.state,
            'file_details': {}
        }
        if job.ready():
            if job.state == 'SUCCESS':
                context['result'] = job.result
            context['is_ready'] = True
            context['is_expired'] = False

        return JsonResponse(context)


class DownloadOptionsViewBase(FormView):
    template_name = 'aristotle_mdr/downloads/download_options.html'
    session_key = 'download_options'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs['no_email'] = False
        if not self.request.user.is_authenticated:
            # If the user is unauthenticated, they don't have an email
            kwargs['no_email'] = True

        return kwargs

    def dispatch(self, request, *args, **kwargs):
        self.download_type = self.kwargs['download_type']
        self.download_class = get_download_class(self.download_type)
        if self.download_class is None:
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['title'] = self.request.GET.get('title', "")
        return initial

    def get_success_url(self):
        if len(self.items) > 1 or self.qs:
            url = reverse('aristotle:bulk_download', args=[self.download_type])
            return url + '?' + self.request.GET.urlencode()
        else:
            url = reverse('aristotle:download', args=[self.download_type, self.items[0]])
            return url

    def form_valid(self, form):
        cleaned_data = form.cleaned_data
        logger.debug('Cleaned data: {}'.format(cleaned_data))

        if form.wrap_pages:
            storage_class = get_storage_class()
            storage = storage_class()

            if self.request.user.is_authenticated:
                prefix = str(self.request.user.id)
            else:
                prefix = 'anon'

            for file_field in ['front_page', 'back_page']:
                uploaded_file = cleaned_data[file_field]
                if uploaded_file:
                    path = '{uid}/{fname}'.format(uid=prefix, fname=uploaded_file.name)
                    saved_fname = storage.save(path, uploaded_file)
                    cleaned_data[file_field] = saved_fname

        self.request.session[self.session_key] = cleaned_data
        return super().form_valid(form)


class DownloadOptionsView(DownloadOptionsViewBase):
    """
    Form with options before the download
    """
    form_class = DownloadOptionsForm

    def dispatch(self, request, *args, **kwargs):
        self.items = request.GET.getlist('items')
        self.qs = request.GET.get('qs')
        if not self.items and not self.qs:
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['wrap_pages'] = self.download_class.allow_wrapper_pages
        return kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        if len(self.items) == 1:
            # It's for a single item, we can add breadcrumbs
            item_id = self.items[0]
            try:
                item_id = int(item_id)
            except ValueError:
                raise Http404
            item = get_object_or_404(MDR._concept, pk=item_id)
            context_data.update({"item_name": item.name,
                                 "item_url": item.get_absolute_url()
                                 })
        return context_data

    def form_valid(self, form):
        cleaned_data = form.cleaned_data
        logger.debug('Cleaned data: {}'.format(cleaned_data))

        if form.wrap_pages:
            storage_class = get_storage_class()
            storage = storage_class()

            if self.request.user.is_authenticated:
                prefix = str(self.request.user.id)
            else:
                prefix = 'anon'

            for file_field in ['front_page', 'back_page']:
                uploaded_file = cleaned_data[file_field]
                if uploaded_file:
                    path = '{uid}/{fname}'.format(uid=prefix, fname=uploaded_file.name)
                    saved_fname = storage.save(path, uploaded_file)
                    cleaned_data[file_field] = saved_fname

        self.request.session[self.session_key] = cleaned_data
        return super().form_valid(form)
