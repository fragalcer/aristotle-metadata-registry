from typing import List, Callable, Any, Dict
from django import forms
from django.core.exceptions import PermissionDenied, FieldDoesNotExist
from django.urls import reverse
from django.db import transaction
from django.forms.models import inlineformset_factory
from django.forms import formset_factory
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, TemplateView, View
from django.views.generic import ListView

from aristotle_mdr.contrib.autocomplete import widgets
from aristotle_mdr.models import AbstractValue, _concept
from aristotle_mdr.perms import user_can_edit, user_can_view
from aristotle_mdr.utils import construct_change_message
from aristotle_mdr.utils.text import capitalize_words
from aristotle_mdr.contrib.generic.forms import (
    ordered_formset_factory, ordered_formset_save,
    one_to_many_formset_excludes, one_to_many_formset_filters,
    HiddenOrderFormset, HiddenOrderInlineFormset,
    get_aristotle_widgets
)
import json
import reversion
import inspect
from copy import copy

import logging
logger = logging.getLogger(__name__)


def generic_foreign_key_factory_view(request, **kwargs):
    item = get_object_or_404(_concept, pk=kwargs['iid']).item
    field = None

    for f in item._meta.fields:
        if f.name.lower() == kwargs['fk_field'].lower():
            field = f.name

    if not field:
        raise Http404

    return GenericAlterForeignKey.as_view(
        model_base=item.__class__,
        model_base_field=field,
        form_title=_('Add Object Class')
    )(request, **kwargs)


class GenericWithItemURLView(View):
    user_checks: List[Callable] = []
    permission_checks: List[Callable] = [user_can_view]
    model_base: object = _concept
    item_kwarg = "iid"

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(self.model_base, pk=self.kwargs[self.item_kwarg])

        if not (
                self.item and
                all([perm(request.user, self.item) for perm in self.permission_checks]) and
                all([perm(request.user) for perm in self.user_checks])
        ):
            if request.user.is_anonymous:
                return redirect(reverse('friendly_login') + '?next=%s' % request.path)
            else:
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['item'] = self.item
        context['submit_url'] = self.request.get_full_path()
        return context

    def get_success_url(self):
        return self.item.get_absolute_url()


class GenericWithItemURLFormView(GenericWithItemURLView, FormView):
    pass


class GenericAlterManyToSomethingFormView(GenericWithItemURLFormView):
    permission_checks: List[Callable] = [user_can_edit]
    model_base: Any = None
    model_to_add: Any = None
    model_base_field = ''
    form_title = ''
    form_submit_text = _('Save')

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['model_to_add'] = self.model_to_add
        context['model_base'] = self.model_base
        context['item'] = self.item
        context['form_title'] = self.form_title or _('Add child item')
        context['form_submit_text'] = self.form_submit_text
        return context


class GenericAlterForeignKey(GenericAlterManyToSomethingFormView):
    """
    A view that provides a framework for altering ManyToOne relationships
    (Include through models from ManyToMany relationships)
    from one 'base' object to many others.

    The URL pattern must pass a kwarg with the name `iid` that is the object from the
    `model_base` to use as the main link for the many to many relation.

    * `model_base` - mandatory - The model with the instance to be altered
    * `model_to_add` - mandatory - The model that has instances we will link to the base.
    * `template_name`
        - optional - The template used to display the form.
        - default - "aristotle_mdr/generic/actions/alter_foreign_key.html"
    * `model_base_field` - mandatory - the name of the field that goes from the `model_base` to the `model_to_add`.
    * `model_to_add_field` - mandatory - the name of the field on the `model_to_add` model that links to the `model_base` model.
    * `form_title` - Title for the form

    For example: If we have a many to many relationship from `DataElement`s to
    `Dataset`s, to alter the `DataElement`s attached to a `Dataset`, `Dataset` is the
    `base_model` and `model_to_add` is `DataElement`.
    """

    template_name = "aristotle_mdr/generic/actions/alter_foreign_key.html"
    model_to_add_field = None
    form = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form_add_another_text'] = self.form_submit_text or _('Add another')
        form = self.form or self.get_form()(instance=self.item)
        context['form'] = form
        return context

    def get_form(self, form_class=None):
        foreign_model = self.model_base._meta.get_field(self.model_base_field).related_model
        qs = foreign_model.objects.visible(self.request.user)
        model_base_field = self.model_base_field

        class FKOnlyForm(forms.ModelForm):
            class Meta:
                model = self.model_base
                fields = (self.model_base_field,)
                widgets = {
                    self.model_base_field: widgets.ConceptAutocompleteSelect(
                        model=foreign_model
                    )
                }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields[model_base_field].queryset = qs

        return FKOnlyForm

    def save_form(self, form):
        """
        Saves the formset returned by the view
        Can be overwritten to add/change extra data
        """
        form.save()

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance with the passed
        POST variables and then checked for validity.
        """
        form = self.get_form()
        self.form = form(self.request.POST, self.request.FILES, instance=self.item)
        if self.form.is_valid():
            with transaction.atomic(), reversion.revisions.create_revision():
                self.save_form(self.form)

                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment(
                    _("Altered relationship of '%s' on %s") % (self.model_base_field, self.item)
                )

            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class GenericAlterManyToManyView(GenericAlterManyToSomethingFormView):
    """
    A view that provides a framework for altering ManyToMany relationships from
    one 'base' object to many others.

    The URL pattern must pass a kwarg with the name `iid` that is the object from the
    `model_base` to use as the main link for the many to many relation.

    * `model_base` - mandatory - The model with the instance to be altered
    * `model_to_add` - mandatory - The model that has instances we will link to the base.
    * `template_name`
        - optional - The template used to display the form.
        - default - "aristotle_mdr/generic/actions/alter_many_to_many.html"
    * `model_base_field` - mandatory - the field name that goes from the `model_base` to the `model_to_add`.
    * `form_title` - Title for the form

    For example: If we have a many to many relationship from `DataElement`s to
    `Dataset`s, to alter the `DataElement`s attached to a `Dataset`, `Dataset` is the
    `base_model` and `model_to_add` is `DataElement`.
    """

    template_name = "aristotle_mdr/generic/actions/alter_many_to_many.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        return context

    def get_form_class(self):
        class M2MForm(forms.Form):
            items_to_add = forms.ModelMultipleChoiceField(
                queryset=self.model_to_add.objects.visible(self.request.user),
                label="Attach",
                required=False,
                widget=widgets.ConceptAutocompleteSelectMultiple(
                    model=self.model_to_add
                )
            )
        return M2MForm

    def get_initial(self):
        return {
            'items_to_add': getattr(self.item, self.model_base_field).all()
        }

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

    def form_valid(self, form):
        m2m_field = getattr(self.item, self.model_base_field)
        m2m_field.set(form.cleaned_data['items_to_add'])

        self.item.save()
        return HttpResponseRedirect(self.get_success_url())


class GenericAlterManyToManyOrderView(GenericAlterManyToManyView):

    template_name = "aristotle_mdr/generic/actions/alter_many_to_many_order.html"

    def get_form_class(self):
        class M2MOrderForm(forms.Form):
            item_to_add = forms.ModelChoiceField(
                queryset=self.model_to_add.objects.visible(self.request.user),
                label="Attach",
                required=False,
                widget=widgets.ConceptAutocompleteSelect(
                    model=self.model_to_add
                )
            )
        return M2MOrderForm

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form_add_another_text'] = _('Add Another')

        if 'formset' in kwargs:
            context['formset'] = kwargs['formset']
        else:
            formset_initial = self.get_formset_initial()
            formset = self.get_formset()(initial=formset_initial)
            context['formset'] = formset

        if 'message' in kwargs:
            context['error_message'] = kwargs['message']

        return context

    def get_form(self, form_class=None):
        return None

    def dispatch(self, request, *args, **kwargs):

        self.through_model = self.model_base._meta.get_field(self.model_base_field).remote_field.through

        self.base_through_field = None
        self.related_through_field = None
        for field in self.through_model._meta.get_fields():
            if field.is_relation:
                if field.related_model == self.model_base:
                    self.base_through_field = field.name
                elif field.related_model == self.model_to_add:
                    self.related_through_field = field.name

        # Check if either is None
        if self.base_through_field is None or self.related_through_field is None:
            return self.error_with_message('Many to Many edit could not be performed on this object')

        return super().dispatch(request, *args, **kwargs)

    def get_formset(self):

        formclass = self.get_form_class()
        return formset_factory(formclass, formset=HiddenOrderFormset, can_order=True, can_delete=True, extra=0)

    def get_formset_initial(self):
        # Build initial
        filter_args = {self.base_through_field: self.item}
        through_items = self.through_model.objects.filter(**filter_args).order_by('order')

        initial = []
        for item in through_items:
            initial.append({
                'item_to_add': getattr(item, self.related_through_field),
                'ORDER': item.order
            })

        return initial

    def error_with_message(self, message):
        return self.render_to_response(self.get_context_data(message=message))

    def formset_invalid(self, formset):
        return self.render_to_response(self.get_context_data(formset=formset))

    def post(self, request, *args, **kwargs):

        formset = self.get_formset()
        filled_formset = formset(self.request.POST)

        if filled_formset.is_valid():
            with transaction.atomic(), reversion.revisions.create_revision():

                model_arglist = []
                change_message = []

                for form in filled_formset.ordered_forms:
                    to_add = form.cleaned_data['item_to_add']

                    if to_add:
                        model_args = {
                            self.base_through_field: self.item,
                            self.related_through_field: to_add,
                            'order': form.cleaned_data['ORDER']
                        }

                        model_arglist.append(model_args)
                        change_message.append('Added {} to {} {}'.format(to_add.name, self.item.name, self.model_base_field))

                # Delete existing links

                through_args = {
                    self.base_through_field: self.item
                }
                self.through_model.objects.filter(**through_args).delete()

                # Create new links
                for model_args in model_arglist:
                    self.through_model.objects.create(**model_args)

                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment(change_message)

            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.formset_invalid(filled_formset)


class GenericAlterOneToManyViewBase(GenericAlterManyToSomethingFormView):
    is_ordered = False
    ordering_field = None
    formset_class: Any = None
    template_name = "aristotle_mdr/generic/actions/alter_one_to_many.html"
    formset_factory = inlineformset_factory
    formset = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form_add_another_text'] = self.form_add_another_text or _('Add another')

        formset = self.formset or self.get_formset()

        context['formset'] = one_to_many_formset_filters(formset, self.item)
        context['form'] = None
        return context

    def get_editable_queryset(self):
        return getattr(self.item, self.model_base_field).all()

    def get_form(self, form_class=None):
        return None

    def get_form_kwargs(self):
        return {}

    def get_formset(self, *args, **kwargs):
        return self.get_formset_class()(
            instance=self.item,
            queryset=self.get_editable_queryset(),
            form_kwargs=self.get_form_kwargs(),
            *args, **kwargs
        )

    def get_formset_factory(self):
        return self.__class__.formset_factory

    def get_formset_class(self):
        extra_excludes = one_to_many_formset_excludes(self.item, self.model_to_add)
        all_excludes = [self.model_to_add_field, ] + extra_excludes
        if self.ordering_field:
            all_excludes.append(self.ordering_field)
        kwargs = {}
        form = self.get_form()

        if form:
            kwargs.update(form=form)
        if self.formset_class:
            kwargs.update(formset=self.formset_class)

        formset = self.get_formset_factory()(
            model=self.model_to_add,
            parent_model=self.model_base,
            fk_name=self.model_to_add_field,
            exclude=all_excludes,
            can_order=self.is_ordered,
            can_delete=True,
            extra=0,
            widgets=get_aristotle_widgets(self.model_to_add, ordering_field=self.ordering_field),
            **kwargs
        )
        formset.is_ordered = self.is_ordered
        if self.ordering_field:
            formset.ordering_field = self.ordering_field
        return formset

    def save_formset(self, formset):
        """
        Saves the instances returned by the formset
        Can be overwritten to add/change extra data
        """
        formset.save()

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests, instantiating a form instance with the passed
        POST variables and then checked for validity.
        """
        form = self.get_form()
        self.formset = self.get_formset(
            self.request.POST, self.request.FILES,
        )
        if self.formset.is_valid():
            with transaction.atomic(), reversion.revisions.create_revision():
                self.item.save()

                self.save_formset(self.formset)

                reversion.revisions.set_user(request.user)
                reversion.revisions.set_comment(construct_change_message(None, [self.formset]))

            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.form_invalid(form)


class GenericAlterOneToManyView(GenericAlterOneToManyViewBase):
    """
    A view that provides a framework for altering ManyToOne relationships
    (Include through models from ManyToMany relationships)
    from one 'base' object to many others.

    The URL pattern must pass a kwarg with the name `iid` that is the object from the
    `model_base` to use as the main link for the many to many relation.

    * `model_base` - mandatory - The model with the instance to be altered
    * `model_to_add` - mandatory - The model that has instances we will link to the base.
    * `template_name`
        - optional - The template used to display the form.
        - default - "aristotle_mdr/generic/actions/alter_many_to_many.html"
    * `model_base_field` - mandatory - the name of the field that goes from the `model_base` to the `model_to_add`.
    * `model_to_add_field` - mandatory - the name of the field on the `model_to_add` model that links to the `model_base` model.
    * `ordering_field` - optional - name of the ordering field, if entered this field is hidden and updated using a drag-and-drop library
    * `form_add_another_text` - optional - string used for the button to add a new row to the form - defaults to "Add another"
    * `form_title` - Title for the form

    For example: If we have a many to many relationship from `DataElement`s to
    `Dataset`s, to alter the `DataElement`s attached to a `Dataset`, `Dataset` is the
    `base_model` and `model_to_add` is `DataElement`.
    """

    model_to_add_field = None
    form_add_another_text = None
    is_ordered = True
    formset_class = HiddenOrderInlineFormset


class UnorderedGenericAlterOneToManyView(GenericAlterOneToManyViewBase):
    """
    A view that provides a framework for altering ManyToOne relationships
    (Include through models from ManyToMany relationships)
    from one 'base' object to many others.

    The URL pattern must pass a kwarg with the name `iid` that is the object from the
    `model_base` to use as the main link for the many to many relation.

    * `model_base` - mandatory - The model with the instance to be altered
    * `model_to_add` - mandatory - The model that has instances we will link to the base.
    * `template_name`
        - optional - The template used to display the form.
        - default - "aristotle_mdr/generic/actions/alter_many_to_many.html"
    * `model_base_field` - mandatory - the name of the field that goes from the `model_base` to the `model_to_add`.
    * `model_to_add_field` - mandatory - the name of the field on the `model_to_add` model that links to the `model_base` model.
    * `ordering_field` - optional - name of the ordering field, if entered this field is hidden and updated using a drag-and-drop library
    * `form_add_another_text` - optional - string used for the button to add a new row to the form - defaults to "Add another"
    * `form_title` - Title for the form

    For example: If we have a many to many relationship from `DataElement`s to
    `Dataset`s, to alter the `DataElement`s attached to a `Dataset`, `Dataset` is the
    `base_model` and `model_to_add` is `DataElement`.
    """
    model_to_add_field = ''
    form_add_another_text = ''
    formset = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['disable_ordering'] = True
        return context


class ExtraFormsetMixin:
    # Mixin of utils function for adding additional formsets to a view
    # extra_formsets must contain formset, type, title and saveargs
    # See EditItemView for example usage

    def save_formsets(self, extra_formsets):
        for formsetinfo in extra_formsets:
            if formsetinfo['saveargs']:
                ordered_formset_save(**formsetinfo['saveargs'])
            else:
                formsetinfo['formset'].save()

    def validate_formsets(self, extra_formsets):
        invalid = False

        for formsetinfo in extra_formsets:
            if not formsetinfo['formset'].is_valid():
                invalid = True

        return invalid

    def get_formset_context(self, extra_formsets):
        context = {}

        for formset_info in extra_formsets:
            type = formset_info['type']

            if type == 'identifiers':
                context['identifier_FormSet'] = formset_info['formset']

            elif type == 'slot':
                context['slots_FormSet'] = formset_info['formset']

            elif type == 'weak':
                if 'weak_formsets' not in context.keys():
                    context['weak_formsets'] = []
                context['weak_formsets'].append({'formset': formset_info['formset'],
                                                 'title': formset_info['title'],
                                                 'editor_help_text': formset_info['editor_help_text'],
                                                 'model': formset_info['item'],
                                                 'field_related_name': formset_info['field_related_name'],
                                                 })

            elif type == 'through':
                if 'through_formsets' not in context.keys():
                    context['through_formsets'] = []
                context['through_formsets'].append({'formset': formset_info['formset'],
                                                    'title': formset_info['title']}
                                                   )

            elif type == 'record_relation':
                context['recordrelation_FormSet'] = formset_info['formset']

            elif type == 'reference_links':
                context['referencelinks_FormSet'] = formset_info['formset']

        return context

    def get_extra_formsets(self, item=None, postdata=None, clone_item=False):
        # Item can be a class or an object
        # This is so we can reuse this function in creation wizards

        extra_formsets = []

        if inspect.isclass(item) or clone_item:
            is_class = True
            add_item = None
        else:
            is_class = False
            add_item = item

        through_list = self.get_m2m_through(item)

        for through in through_list:

            if not is_class:
                formset = self.get_order_formset(through, item, postdata)
            else:
                formset = self.get_order_formset(through, postdata=postdata)

            formset = one_to_many_formset_filters(formset, item)

            extra_formsets.append({
                'formset': formset,
                'type': 'through',
                'title': through['field_name'].title(),
                'saveargs': {
                    'formset': formset,
                    'item': add_item,
                    'model_to_add_field': through['item_field'],
                    'ordering_field': 'order'
                }
            })

        weak_list = self.get_m2m_weak(item)

        for weak in weak_list:

            if clone_item:
                formset = self.get_weak_formset(weak, item, clone=True)
            elif not is_class:
                formset = self.get_weak_formset(weak, item, postdata)
            else:
                formset = self.get_weak_formset(weak, postdata=postdata)

            formset = one_to_many_formset_filters(formset, item)

            if hasattr(weak['model'], 'ordering_field'):
                order_field = weak['model'].ordering_field
            else:
                order_field = 'order'

            extra_formsets.append({
                'item': item,
                'formset': formset,
                'type': 'weak',
                'title': weak['model']._meta.verbose_name.title(),
                'editor_help_text': getattr(weak['model'], 'editor_help_text', ''),
                'field_related_name': weak['field_related_name'],
                'saveargs': {
                    'formset': formset,
                    'item': add_item,
                    'model_to_add_field': weak['item_field'],
                    'ordering_field': order_field
                }
            })

        return extra_formsets

    def get_order_formset(self, through, item=None, postdata=None):
        excludes = ['order', through['item_field']]
        formset = ordered_formset_factory(
            through['model'], exclude=excludes,
            ordering_field='order',
        )

        fsargs = {'prefix': through['field_name']}

        if through['item_field']:
            if item:
                through_filter = {through['item_field']: item}
                fsargs['queryset'] = through['model'].objects.filter(**through_filter)
            else:
                fsargs['queryset'] = through['model'].objects.none()

        if postdata:
            fsargs['data'] = postdata

        formset_instance = formset(**fsargs)

        return formset_instance

    def get_weak_formset(self, weak, item=None, postdata=None, clone=False):

        model_to_add_field = weak['item_field']

        if 'prefix' in weak:
            fsargs = {'prefix': weak['prefix']}
        else:
            fsargs = {'prefix': weak['field_name']}

        if item and not clone:
            extra_excludes = one_to_many_formset_excludes(item, weak['model'])
            fsargs['queryset'] = getattr(item, weak['field_name']).all()
        else:
            if issubclass(weak['model'], AbstractValue):
                extra_excludes = ['value_meaning']
            else:
                extra_excludes = []
            fsargs['queryset'] = weak['model'].objects.none()

        extra = 0
        if clone:
            initial = []
            from django.forms.models import model_to_dict
            for index, obj in enumerate(getattr(item, weak['field_name']).all()):
                o = model_to_dict(obj)
                o['ORDER'] = o.pop(weak['model'].ordering_field)
                for k in ['pk', 'id']:  # TODO: do we need to remove the FK field? eg. 'valueDomain'
                    o.pop(k, None)
                initial.append(o)
            fsargs['initial'] = initial
            extra = len(initial)

        if postdata:
            fsargs['data'] = postdata

        all_excludes = [model_to_add_field, weak['model'].ordering_field] + extra_excludes
        formset = ordered_formset_factory(
            weak['model'], exclude=all_excludes,
            extra=extra,
            ordering_field=weak['model'].ordering_field
        )

        final_formset = formset(**fsargs)

        return final_formset

    def get_slots_formset(self):
        from aristotle_mdr.contrib.slots.forms import slot_inlineformset_factory

        formset = slot_inlineformset_factory()

        formset.filtered_empty_form = formset.empty_form

        return formset

    def get_recordrelations_formset(self):
        from aristotle_mdr.forms.creation_wizards import record_relation_inlineformset_factory

        formset = record_relation_inlineformset_factory()

        formset.filtered_empty_form = formset.empty_form

        return formset

    def get_referencelinks_formset(self):
        from aristotle_mdr.forms.creation_wizards import reference_link_inlineformset_factory

        formset = reference_link_inlineformset_factory()

        formset.filtered_empty_form = formset.empty_form

        return formset

    def get_identifier_formset(self):
        from aristotle_mdr.contrib.identifiers.forms import identifier_inlineformset_factory

        formset = identifier_inlineformset_factory()

        formset.filtered_empty_form = formset.empty_form

        return formset

    def get_model_field(self, model, search_model):
        # get the field in the model that we are adding so it can be excluded from form
        model_to_add_field = ''
        for field in model._meta.get_fields():
            if (field.is_relation):
                if (field.related_model == search_model):
                    model_to_add_field = field.name
                    break

        return model_to_add_field

    def get_m2m_through(self, item):
        through_list = []

        if inspect.isclass(item):
            check_class = item
        else:
            check_class = item.__class__

        excludes = getattr(check_class, 'through_edit_excludes', [])
        if not excludes:
            excludes = []

        for field in check_class._meta.get_fields():
            if field.many_to_many:
                if hasattr(field.remote_field, 'through'):
                    through = field.remote_field.through
                    if not through._meta.auto_created:
                        item_field = self.get_model_field(through, check_class)
                        if item_field and field.name not in excludes:
                            through_list.append({'field_name': field.name, 'model': through, 'item_field': item_field})

        return through_list

    def get_m2m_weak(self, item):
        weak_list = []

        if inspect.isclass(item):
            check_class = item
        else:
            check_class = item.__class__

        excludes = getattr(check_class, 'edit_page_excludes', [])
        if not excludes:
            excludes = []

        if hasattr(check_class, 'serialize_weak_entities'):

            weak = check_class.serialize_weak_entities

            for entity in weak:

                if entity[0] not in excludes:

                    if entity[1].endswith('_set'):
                        # entity[1] contains the related name for an object
                        # This can be different to the relation name on the model
                        # If related_name was not set on the foreign key
                        # this code deals with the case where it was auto generated by django
                        related_name = entity[1][:-4]
                    else:
                        related_name = entity[1]

                    try:
                        field = check_class._meta.get_field(entity[1])
                    except FieldDoesNotExist:
                        try:
                            field = check_class._meta.get_field(related_name)
                        except FieldDoesNotExist:
                            continue

                    item_field = self.get_model_field(field.related_model, check_class)
                    if item_field:
                        weak_list.append({'prefix': entity[0],
                                          'field_name': entity[1],
                                          'model': field.related_model,
                                          'item_field': item_field,
                                          'field_related_name': related_name
                                          })

        return weak_list


class ConfirmDeleteView(GenericWithItemURLView, TemplateView):
    confirm_template = "aristotle_mdr/generic/actions/confirm_delete.html"
    template_name = "aristotle_mdr/generic/actions/confirm_delete.html"
    form_delete_button_text = _("Delete")
    warning_text = _("You are about to delete something, confirm below, or click cancel to return to the item.")
    form_title = "Delete item"

    # Default to concept
    reverse_url = 'aristotle:item'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['form_title'] = self.form_title
        context['form_delete_button_text'] = self.form_delete_button_text
        context['warning_text'] = self.get_warning_text()
        context['reverse_url'] = self.reverse_url
        return context

    def get_warning_text(self):
        return self.warning_text

    def perform_deletion(self):
        raise NotImplementedError("This must be overridden in a subclass")

    def post(self, *args, **kwargs):
        self.perform_deletion()
        return HttpResponseRedirect(self.get_success_url())


class BootTableListView(ListView):
    """Lists objects in a bootstrap table (with optional pagination)"""
    template_name = 'aristotle_mdr/generic/boottablelist.html'
    # Need to override these
    headers: List[str]
    attrs: List[str]
    model_name = ''
    # Can optionally override these
    blank_value: Dict[str, str]
    page_heading = ''
    create_button_text = ''
    create_url_name = ''
    delete_url_name = ''
    update_url_name = ''

    def get_heading(self) -> str:
        if self.page_heading:
            return self.page_heading
        else:
            return 'List of {}s'.format(self.model_name)

    def get_create_text(self) -> str:
        if self.create_button_text:
            return self.create_button_text
        else:
            return 'New {}'.format(self.model_name)

    def get_listing(self, iterable) -> List[Dict]:
        listing = []
        for item in iterable:
            itemdict = {'attrs': [], 'pk': item.pk}
            for attr in self.attrs:
                val = getattr(item, attr)
                if not val and attr in self.blank_value:
                    val = self.blank_value[attr]
                itemdict['attrs'].append(val)
            listing.append(itemdict)

        return listing

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data()
        headers = copy(self.headers)

        page_heading = self.get_heading()
        create_button_text = self.get_create_text()

        if self.create_url_name:
            create_url = reverse(self.create_url_name)
        else:
            create_url = ''

        if self.update_url_name:
            headers.append('Update')
        if self.delete_url_name:
            headers.append('Delete')

        if context['page_obj'] is not None:
            iterable = context['page_obj']
        else:
            iterable = context['object_list']

        final_list = self.get_listing(iterable)

        context.update({
            'list': final_list,
            'headers': headers,
            'page_heading': page_heading,
            'create_button_text': create_button_text,
            'create_url': create_url,
            'delete_url_name': self.delete_url_name,
            'update_url_name': self.update_url_name
        })
        return context


class CancelUrlMixin:
    cancel_url_name = ''

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if self.cancel_url_name:
            context['cancel_url'] = reverse(self.cancel_url_name)
        return context


class VueFormView(FormView):
    """
    A view for returning a serialized json representation of a django form
    for use with vue components. Does not permit the POST method as that
    should be handled by the api
    """

    # Mapping of widgets to extra fields data
    widget_mapping: Dict[str, Dict] = {
        'Textarea': {'tag': 'textarea'},
        'Select': {'tag': 'select'},
    }

    # Attributes to pull from field as rules
    rules_attrs_to_pull: List[str] = ['required', 'max_length', 'min_length']

    # Base field data
    default_tag = 'input'

    # Fields to strip from initial
    non_write_fields: List = []
    # Wether to capitalize option names
    capitalize_options: bool = True

    def get_vue_initial(self):
        # To be overwritten
        return {}

    def strip_fields(self, data: List[Dict]):
        for fname in self.non_write_fields:
            if fname in data:
                del data[fname]

    def get_vue_form_fields(self, form: forms.Form) -> Dict[str, Dict]:
        vuefields = {}
        for fname, field in form.fields.items():
            widget_name = type(field.widget).__name__

            # Data that is used to render the field in the Vue template
            field_data = {
                'rules': {},
                'help_text': field.help_text,
                'tag': self.default_tag,
                'label': field.label,
                'options': [],
                'default': field.initial
            }

            if widget_name in self.widget_mapping:
                field_data.update(self.widget_mapping[widget_name])

            if widget_name == 'Select':
                # field.choices can be an iterator hence the need for this
                field_data['options'] = [[c[0], c[1]] for c in field.choices]

                if self.capitalize_options:
                    for item in field_data['options']:
                        item[1] = capitalize_words(item[1])

            for attr in self.rules_attrs_to_pull:
                if hasattr(field, attr):
                    attrdata = getattr(field, attr)
                    if attrdata:
                        field_data['rules'][attr] = attrdata

            vuefields[fname] = field_data

        return vuefields

    def post(self, request, *args, **kwargs):
        return self.http_method_not_allowed(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data()
        context['vue_fields'] = json.dumps(
            self.get_vue_form_fields(context['form'])
        )

        initial = self.get_vue_initial()

        self.strip_fields(initial)

        context['vue_initial'] = json.dumps(initial)

        return context
