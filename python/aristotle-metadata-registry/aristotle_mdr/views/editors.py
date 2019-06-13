from django.http import HttpResponseRedirect
from django.views.generic import UpdateView, FormView
from django.views.generic.detail import SingleObjectMixin

import reversion
from reversion.models import Version

from aristotle_mdr.utils import (
    concept_to_clone_dict, construct_change_message_extra_formsets,
    url_slugify_concept, is_active_module, cloud_enabled
)

from aristotle_mdr import forms as MDRForms
from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.publishing.models import VersionPermissions

from aristotle_mdr.views.utils import ObjectLevelPermissionRequiredMixin
from aristotle_mdr.contrib.help.models import ConceptHelp
from aristotle_mdr.contrib.identifiers.models import ScopedIdentifier
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.contrib.custom_fields.forms import CustomValueFormMixin
from aristotle_mdr.contrib.custom_fields.models import CustomField, CustomValue

import logging

from aristotle_mdr.contrib.generic.views import ExtraFormsetMixin

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class ConceptEditFormView(ObjectLevelPermissionRequiredMixin):
    """
    Base class for editing concepts
    """
    raise_exception = True
    redirect_unauthenticated_users = True
    object_level_permissions = True
    model = MDR._concept
    pk_url_kwarg = 'iid'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: introduce better behavior for this
        self.additional_records_active = True
        self.reference_links_active = cloud_enabled()

        self.slots_active = is_active_module('aristotle_mdr.contrib.slots')
        self.identifiers_active = is_active_module('aristotle_mdr.contrib.identifiers')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.item = self.object.item
        self.model = self.item.__class__
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({
            'model_name_plural': self.model._meta.verbose_name_plural.title,
            'model': self.model._meta.model_name,
            'app_label': self.model._meta.app_label,
            'item': self.item,
            'model_class': self.model,
            'help': ConceptHelp.objects.filter(
                app_label=self.model._meta.app_label,
                concept_type=self.model._meta.model_name
            ).first(),
        })

        if cloud_enabled():
            from aristotle_cloud.contrib.custom_help.models import CustomHelp
            context.update({
                "custom_help": CustomHelp.objects.filter(
                    content_type__app_label=self.model._meta.app_label,
                    content_type__model=self.model._meta.model_name,
                ).first()
            })

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'user': self.request.user,
            'custom_fields': CustomField.objects.get_for_model(type(self.item), user=self.request.user)
        })
        return kwargs

    def get_custom_values(self):
        # If we are editing, must be able to see the content added to a custom value
        return CustomValue.objects.get_for_item(self.item.concept)

    def get_initial(self):
        initial = super().get_initial()
        cvs = self.get_custom_values()
        for cv in cvs:
            fname = cv.field.form_field_name
            initial[fname] = cv.content

        return initial

    def form_invalid(self, form, formsets=None):
        """
        If the form is invalid, re-render the context data with the
        data-filled form and errors.
        """

        return self.render_to_response(self.get_context_data(form=form, formsets=formsets))


class EditItemView(ExtraFormsetMixin, ConceptEditFormView, UpdateView):
    template_name = "aristotle_mdr/actions/advanced_editor.html"
    permission_required = "aristotle_mdr.user_can_edit"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'instance': self.item,
        })
        return kwargs

    def get_form_class(self):
        return MDRForms.wizards.subclassed_edit_modelform(
            self.model,
            extra_mixins=[CustomValueFormMixin]
        )

    def get_extra_formsets(self, item=None, postdata=None):
        extra_formsets = super().get_extra_formsets(item, postdata)

        if self.slots_active:
            slot_formset = self.get_slots_formset()(
                queryset=Slot.objects.filter(concept=self.item.id),
                instance=self.item.concept,
                data=postdata
            )

            extra_formsets.append({
                'formset': slot_formset,
                'title': 'Slots',
                'type': 'slot',
                'saveargs': None
            })

        if self.additional_records_active:
            recordrelation_formset = self.get_recordrelations_formset()(
                instance=self.item.concept,
                data=postdata
            )

            # Override the queryset to restrict to the records the user has permission to view
            for record_relation_form in recordrelation_formset:
                record_relation_form.fields['organization_record'].queryset = MDR.OrganizationRecord.objects.visible(self.request.user).order_by("name")

            extra_formsets.append({
                'formset': recordrelation_formset,
                'title': 'RecordRelation',
                'type': 'record_relation',
                'saveargs': None
            })

        if self.reference_links_active:
            recordrelation_formset = self.get_referencelinks_formset()(
                instance=self.item.concept,
                data=postdata
            )
            from aristotle_cloud.contrib.steward_extras.models import ReferenceBase

            # Override the queryset to restrict to the records the user has permission to view
            for record_relation_form in recordrelation_formset:
                record_relation_form.fields['reference'].queryset = ReferenceBase.objects.visible(self.request.user).order_by("title")

            extra_formsets.append({
                'formset': recordrelation_formset,
                'title': 'ReferenceLink',
                'type': 'reference_links',
                'saveargs': None
            })

        if self.identifiers_active:
            id_formset = self.get_identifier_formset()(
                queryset=ScopedIdentifier.objects.filter(concept=self.item.id),
                instance=self.item.concept,
                data=postdata
            )

            extra_formsets.append({
                'formset': id_formset,
                'title': 'Identifiers',
                'type': 'identifiers',
                'saveargs': None
            })

        return extra_formsets

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        extra_formsets = self.get_extra_formsets(self.item, request.POST)

        self.object = self.item

        if form.is_valid():
            # Actualize the model, but don't save just yet
            item = form.save(commit=False)
            change_comments = form.data.get('change_comments', None)
            form_invalid = False
        else:
            form_invalid = True

        formsets_invalid = self.validate_formsets(extra_formsets)

        if form_invalid or formsets_invalid:
            return self.form_invalid(form, formsets=extra_formsets)
        else:
            # The form and the formsets were valid
            # This was removed from the revision below due to a bug with saving
            # long slots, links are still saved due to reversion follows
            self.save_formsets(extra_formsets)

            # Create the revision
            with reversion.revisions.create_revision():
                if not change_comments:
                    # If there were no change comments made in the form
                    change_comments = construct_change_message_extra_formsets(request, form, extra_formsets)

                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment(change_comments)

                # Update the item
                form.save_m2m()
                item.save()
                form.save_custom_fields(item)

            # Versions are loaded with the most recent version first, so we get the one that was just created
            version = Version.objects.get_for_object(item).first()
            VersionPermissions.objects.create(version=version)

            return HttpResponseRedirect(url_slugify_concept(self.item))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        invalid_tabs = set()
        # We get formset passed on errors
        if 'formsets' in kwargs:
            extra_formsets = kwargs['formsets']
            for item in extra_formsets:
                if item['formset'].errors:
                    if item['type'] in ('weak', 'through'):
                        invalid_tabs.add('Components')
                    else:
                        invalid_tabs.add(item['title'])
        else:
            extra_formsets = self.get_extra_formsets(self.item)

        context['invalid_tabs'] = invalid_tabs

        fscontext = self.get_formset_context(extra_formsets)
        context.update(fscontext)

        context['show_slots_tab'] = self.slots_active or context['form'].custom_fields
        context['slots_active'] = self.slots_active
        context['show_id_tab'] = self.identifiers_active

        context['additional_records_active'] = self.additional_records_active
        context['reference_links_active'] = self.reference_links_active

        return context


class CloneItemView(ExtraFormsetMixin, ConceptEditFormView, SingleObjectMixin, FormView):
    template_name = "aristotle_mdr/create/clone_item.html"
    permission_required = "aristotle_mdr.user_can_view"

    def get_form_class(self):
        return MDRForms.wizards.subclassed_clone_modelform(
            self.model,
            extra_mixins=[CustomValueFormMixin]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = concept_to_clone_dict(self.item)

        from aristotle_mdr.contrib.custom_fields.models import CustomValue
        for custom_val in CustomValue.objects.get_item_allowed(self.item, self.request.user):
            initial[custom_val.field.form_field_name] = custom_val.content

        kwargs.update({
            'initial': initial
        })
        return kwargs

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        extra_formsets = self.get_extra_formsets(self.model, request.POST)

        if form.is_valid():
            item = form.save(commit=False)
            item.submitter = request.user
            change_comments = form.data.get('change_comments', None)
            form_invalid = False
        else:
            form_invalid = True

        formsets_invalid = self.validate_formsets(extra_formsets)
        invalid = form_invalid or formsets_invalid

        if invalid:
            return self.form_invalid(form, formsets=extra_formsets)
        else:
            with reversion.revisions.create_revision():
                if not change_comments:
                    change_comments = construct_change_message_extra_formsets(request, form, extra_formsets)

                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment(change_comments)

                # Save item
                item.save()
                form.save_custom_fields(item)
                form.save_m2m()

            # Copied from wizards.py - maybe refactor
            final_formsets = []
            for info in extra_formsets:
                if info['type'] != 'slot':
                    info['saveargs']['item'] = item
                else:
                    info['formset'].instance = item
                final_formsets.append(info)

            # This was removed from the revision below due to a bug with saving
            # long slots, links are still saved due to reversion follows
            self.save_formsets(final_formsets)

            return HttpResponseRedirect(url_slugify_concept(item))

    def clone_components(self, clone):
        original = self.item
        fields = getattr(self.model, 'clone_fields', [])
        for field_name in fields:
            field = self.model._meta.get_field(field_name)
            remote_field_name = field.remote_field.name
            manager = getattr(original, field.get_accessor_name(), None)
            if manager is None:
                components = []
            else:
                components = manager.all()

            new_components = []
            for component in components:
                # Set pk to none so we insert instead of update
                component.pk = None
                # Set the remote field to the clone
                setattr(component, remote_field_name, clone)
                new_components.append(component)
            field.related_model.objects.bulk_create(new_components)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        if 'formsets' in kwargs:
            extra_formsets = kwargs['formsets']
        else:
            extra_formsets = self.get_extra_formsets(self.item, clone_item=True)

        fscontext = self.get_formset_context(extra_formsets)
        context.update(fscontext)

        context['show_slots_tab'] = context['form'].custom_fields
        context['show_id_tab'] = self.identifiers_active

        return context
