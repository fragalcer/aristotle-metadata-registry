from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db import transaction
from django.db.models.query import Prefetch
from django.forms.models import modelformset_factory
from django.http import HttpResponseRedirect, Http404
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import ugettext as _

import reversion

from aristotle_mdr import models as aristotle_models
from aristotle_mdr.contrib.generic.views import ConfirmDeleteView
from aristotle_mdr.contrib.generic.forms import HiddenOrderModelFormSet
from aristotle_mdr.perms import (
    user_can_view, user_can_edit, user_in_workgroup,
    user_is_workgroup_manager, user_can_add_status
)
from aristotle_mdr.utils import construct_change_message
from aristotle_mdr.views.utils import get_status_queryset
from aristotle_mdr.views.views import ConceptRenderView

from aristotle_dse import forms, models


def addDataElementsToDSS(request, dss_id):
    dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
    if not user_can_edit(request.user, dss):
        raise PermissionDenied
    qs = aristotle_models.DataElement.objects.filter().visible(request.user)
    if request.method == 'POST':
        form = forms.AddDataElementsToDSSForm(request.POST, user=request.user, qs=qs, dss=dss)
        if form.is_valid():
            inclusion = form.cleaned_data['inclusion']
            maxOccurs = form.cleaned_data['maximum_occurrences']
            with reversion.revisions.create_revision():
                for de in form.cleaned_data['dataElements']:
                    dss.addDataElement(
                        data_element=de,
                        maximum_occurrences=maxOccurs,
                        inclusion=inclusion
                    )
                dss.save()
                reversion.set_comment('Added data elements')
            return HttpResponseRedirect(reverse("aristotle_mdr:item", args=[dss.id]))
    else:
        form = forms.AddDataElementsToDSSForm(user=request.user, qs=qs, dss=dss)

    return render(
        request,
        "aristotle_dse/actions/addDataElementsToDSS.html",
        {
            "item": dss,
            "form": form,
        }
    )


def addClustersToDSS(request, dss_id):
    dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
    if not user_can_edit(request.user, dss):
        raise PermissionDenied
    qs = models.DataSetSpecification.objects.filter().visible(request.user)
    if request.method == 'POST':
        form = forms.AddClustersToDSSForm(request.POST, user=request.user, qs=qs, dss=dss)
        if form.is_valid():
            inclusion = form.cleaned_data['inclusion']
            maxOccurs = form.cleaned_data['maximum_occurrences']
            with reversion.revisions.create_revision():
                for child_dss in form.cleaned_data['clusters']:
                    dss.addCluster(
                        child=child_dss,
                        maximum_occurrences=maxOccurs,
                        inclusion=inclusion
                    )
                dss.save()
                reversion.set_comment('Added clusters')
            return HttpResponseRedirect(reverse("aristotle_mdr:item", args=[dss.id]))
    else:
        form = forms.AddClustersToDSSForm(user=request.user, qs=qs, dss=dss)

    return render(
        request,
        "aristotle_dse/actions/addClustersToDSS.html",
        {
            "item": dss,
            "form": form,
        }
    )


class RemoveDEFromDSS(ConfirmDeleteView):
    item_kwarg="dss_id"
    form_title="Remove data element from dataset"
    form_delete_button_text="Remove data element"

    def perform_deletion(self):
        de_id = self.kwargs['de_id']
        dss_id = self.kwargs['dss_id']
        de = get_object_or_404(aristotle_models.DataElement, id=de_id)
        dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
        if user_can_view(self.request.user, de) and user_can_edit(self.request.user, dss):
            with reversion.revisions.create_revision():
                dss.dssdeinclusion_set.filter(data_element=de).delete()
                dss.save()
                reversion.set_comment('Removed {}'.format(de.name))
            messages.success(
                self.request,
                _('The Data Element "%(de_name)s" was removed from the dataset "%(dss_name)s".') % {
                    "de_name": de.name, "dss_name": dss.name
                }
            )
        else:
            raise PermissionDenied

    def warning_text(self):
        de = get_object_or_404(aristotle_models.DataElement, id=self.kwargs['de_id'])
        dss = get_object_or_404(models.DataSetSpecification, id=self.kwargs['dss_id'])
        return _(
            'You are about to detatch the data element "%(de_name)s" from the dataset "%(dss_name)s". \n'
            'This data element will still exist in the registry, but will no longer be linked to this Data Set Specification. \n\n'
            'Click "Remove data element" below to confirm, or click "Cancel" to return'
        ) % {
            "de_name": de.name, "dss_name": dss.name
        }


class RemoveClusterFromDSS(ConfirmDeleteView):
    item_kwarg="dss_id"
    form_title="Remove data element from this dataset"

    def perform_deletion(self):
        cluster_id = self.kwargs['cluster_id']
        dss_id = self.kwargs['dss_id']
        cluster = get_object_or_404(models.DataSetSpecification, id=cluster_id)
        dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
        if user_can_view(self.request.user, cluster) and user_can_edit(self.request.user, dss):
            with reversion.revisions.create_revision():
                dss.dssclusterinclusion_set.filter(child=cluster).delete()
                dss.save()
                reversion.set_comment('Removed {}'.format(cluster.name))
            messages.success(
                self.request,
                _('The cluster "%(cl_name)s" was removed from the dataset "%(dss_name)s".') % {
                    "cl_name": cluster.name, "dss_name": dss.name
                }
            )
        else:
            raise PermissionDenied


def editDataElementInclusion(request, dss_id, de_id):
    dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
    de = get_object_or_404(aristotle_models.DataElement, id=de_id)
    if not (user_can_edit(request.user, dss) and user_can_view(request.user, de)):
        raise PermissionDenied
    inclusion = get_object_or_404(models.DSSDEInclusion, data_element=de, dss=dss)

    if request.method == 'POST':
        form = forms.EditDataElementInclusionForm(request.POST, instance=inclusion)  # , user=request.user)
        if form.is_valid():
            with reversion.revisions.create_revision():
                form.save()
                dss.save()
                reversion.set_comment('Edited data element inclusion')
            return HttpResponseRedirect(reverse("aristotle_mdr:item", args=[dss.id]))
    else:
        form = forms.EditDataElementInclusionForm(instance=inclusion)  # , user=request.user)

    return render(
        request,
        "aristotle_dse/actions/edit_inclusion.html",
        {
            "item": inclusion,
            "form": form,
        }
    )


def editClusterInclusion(request, dss_id, cluster_id):
    dss = get_object_or_404(models.DataSetSpecification, id=dss_id)
    cluster = get_object_or_404(models.DataSetSpecification, id=cluster_id)
    if not (user_can_edit(request.user, dss) and user_can_view(request.user, cluster)):
        raise PermissionDenied
    inclusion = get_object_or_404(models.DSSClusterInclusion, child=cluster, dss=dss)

    if request.method == 'POST':
        form = forms.EditClusterInclusionForm(request.POST, instance=inclusion)  # , user=request.user)
        if form.is_valid():
            with reversion.revisions.create_revision():
                form.save()
                dss.save()
                reversion.set_comment('Edited cluster inclusion')
            return HttpResponseRedirect(reverse("aristotle_mdr:item", args=[dss.id]))
    else:
        form = forms.EditClusterInclusionForm(instance=inclusion)  # , user=request.user)

    return render(
        request,
        "aristotle_dse/actions/edit_inclusion.html",
        {
            "item": inclusion,
            "form": form,
        }
    )


def editInclusionDetails(request, dss_id, inc_type, cluster_id):
    dss = get_object_or_404(models.DataSetSpecification, id=dss_id)

    if inc_type not in ['cluster', 'data_element']:
        raise Http404
    item = get_object_or_404(models.DataSetSpecification, pk=dss_id)
    if not user_can_edit(request.user, item):
        if request.user.is_anonymous:
            return redirect(reverse('friendly_login') + '?next=%s' % request.path)
        else:
            raise PermissionDenied

    item_type, field_name = {
        'cluster': (models.DataSetSpecification, 'child'),
        'data_element': (aristotle_models.DataElement, 'data_element'),
        }.get(inc_type)

    cluster=get_object_or_404(item_type, id=cluster_id)
    if not (user_can_edit(request.user, dss) and user_can_view(request.user, cluster_id)):
        raise PermissionDenied
    inclusion = get_object_or_404(models.DSSClusterInclusion, child=cluster, dss=dss)

    if request.method == 'POST':
        form = forms.EditClusterInclusionForm(request.POST, instance=inclusion)  # , user=request.user)
        if form.is_valid():
            with reversion.revisions.create_revision():
                form.save()
                dss.save()
                reversion.set_comment('Edited inclusion details')
            return HttpResponseRedirect(reverse("aristotle_mdr:item", args=[dss.id]))
    else:
        form = forms.EditClusterInclusionForm(instance=inclusion)  # , user=request.user)

    return render(
        request,
        "aristotle_dse/actions/edit_inclusion.html",
        {
            "item": inclusion,
            "form": form,
            "include_type": inc_type,
        }
    )


def editInclusionOrder(request, dss_id, inc_type):
    if inc_type not in ['cluster', 'data_element']:
        raise Http404
    item = get_object_or_404(models.DataSetSpecification, pk=dss_id)
    if not user_can_edit(request.user, item):
        if request.user.is_anonymous:
            return redirect(reverse('friendly_login') + '?next=%s' % request.path)
        else:
            raise PermissionDenied

    item_type, field_name = {
        'cluster': (models.DSSClusterInclusion, 'child'),
        'data_element': (models.DSSDEInclusion, 'data_element'),
        }.get(inc_type)

    num_values = item_type.objects.filter(dss=item.id).count()
    if num_values > 0:
        extra = 0
    else:
        extra = 1

    ValuesFormSet = modelformset_factory(
        item_type,
        formset=HiddenOrderModelFormSet,
        can_order=True,
        fields=('id',),
        extra=extra
    )

    if request.method == 'POST':
        formset = ValuesFormSet(request.POST, request.FILES)
        if formset.is_valid():
            with transaction.atomic(), reversion.create_revision():
                item.save()  # do this to ensure we are saving reversion records for the DSS, not just the values
                formset.save(commit=False)
                for form in formset.forms:
                    if form['id'].value() not in [deleted_record['id'].value() for deleted_record in formset.deleted_forms]:
                        inc = item_type.objects.get(pk=form['id'].value())
                        if inc.dss != item:
                            raise PermissionDenied
                        inc.order = form['ORDER'].value()
                        # inc.maximum_occurrences = form['maximum_occurrences'].value()
                        # value = form.save(commit=False) #Don't immediately save, we need to attach the value domain
                        # value.dss = item
                        inc.save()
                for obj in formset.deleted_objects:
                    obj.delete()
                reversion.set_user(request.user)
                reversion.set_comment(construct_change_message(request, None, [formset, ]))

                return redirect(reverse("aristotle_mdr:item", args=[item.id]))
    else:
        formset = ValuesFormSet(
            queryset=item_type.objects.filter(dss=item.id),
        )
    return render(
        request,
        "aristotle_dse/actions/edit_inclusion_order.html",
        {'item': item, 'formset': formset, 'include_type': inc_type, 'value_model': item_type, }
    )


class DynamicTemplateView(TemplateView):
    def get_template_names(self):
        return ['aristotle_dse/static/%s.html' % self.kwargs['template']]


class DatasetSpecificationView(ConceptRenderView):

    objtype = models.DataSetSpecification
    modelslug_arg = None
    slug_redirect = True

    def check_item(self, item):
        return user_can_view(self.request.user, item)

    def get_related(self, model):
        related_objects = [
            'statistical_unit',
        ]
        prefetch_objects = [
            'statuses',
        ]
        qs = model.objects.select_related(*related_objects).prefetch_related(*prefetch_objects)

        valid_statuses = get_status_queryset()

        dssdeinclusions = (
            models.DSSDEInclusion.objects
            .select_related('data_element', "data_element__valueDomain",  "data_element__valueDomain__data_type")
            .prefetch_related(
                Prefetch('data_element__statuses', valid_statuses, 'valid_statuses')
            )

        )

        dssclusterinclusions = (
            models.DSSClusterInclusion.objects
            .select_related('child')
            .prefetch_related(
                Prefetch('child__statuses', valid_statuses, 'valid_statuses')
            )

        )

        qs = qs.prefetch_related(Prefetch('dssdeinclusion_set', dssdeinclusions))
        qs = qs.prefetch_related(Prefetch('dssclusterinclusion_set', dssclusterinclusions))
        return qs

    def grouped(self):
        dss_is_grouped = False
        ungrouped_name = "Data Elements"
        for g in self.item.groups.order_by('order'):
            ungrouped_name = "Ungrouped Data Elements"
            dss_is_grouped = True
            yield g
        yield {
            "name": ungrouped_name,
            "ungrouped": True,
            "dssdeinclusion_set": self.item.ungrouped_data_element_inclusions()
        }

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['groups_with_data_elements'] = self.grouped()
        return context
