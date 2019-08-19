from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist, PermissionDenied
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.db import transaction

from aristotle_mdr import models as MDR
from aristotle_mdr import forms as MDRForms
from aristotle_mdr.utils import url_slugify_concept
from aristotle_mdr.contrib.custom_fields.models import CustomField
from aristotle_mdr.contrib.help.models import ConceptHelp
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.utils import (
    cloud_enabled,
    fetch_aristotle_settings,
    fetch_metadata_apps,
    is_active_module
)
from aristotle_mdr.contrib.generic.views import ExtraFormsetMixin

from formtools.wizard.views import SessionWizardView
from reversion import revisions as reversion

import logging
logger = logging.getLogger(__name__)


def make_it_clean(string):
    return str(strip_tags(string)).replace("&nbsp;", " ").strip()  # Clean it up


def create_item(request, app_label=None, model_name=None):
    """
    This allows use to perform an inspection of the registered items
    so extensions don't need to register to get fancy creation wizards,
    they are available based on either the model name, or if that is
    ambiguous, present an option to make the right item.
    """

    if not model_name:
        raise ImproperlyConfigured
    model_name = model_name.lower()

    mod = None
    if app_label is None:
        models = ContentType.objects.filter(app_label__in=fetch_metadata_apps()).filter(model=model_name)
        if models.count() == 0:
            raise Http404
        elif models.count() == 1:
            mod = models.first().model_class()
        else:
            # Models count is greater than one
            return render(request, "aristotle_mdr/ambiguous_create_request.html", {'models': models})
    else:
        try:
            mod = ContentType.objects.filter(app_label__in=fetch_metadata_apps()).get(app_label=app_label, model=model_name).model_class()
        except ObjectDoesNotExist:
            raise Http404

    class DynamicAristotleWizard(ConceptWizard):
        model = mod
    return DynamicAristotleWizard.as_view()(request)


class PermissionWizard(SessionWizardView):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_active:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.templates[self.steps.current]]

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step)
        kwargs.update({'user': self.request.user})
        return kwargs

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context.update({
            'model': self.model._meta.model_name,
            'app_label': self.model._meta.app_label,
        })
        return context


class ConceptWizard(ExtraFormsetMixin, PermissionWizard):
    """ Concept Wizard is the simple two stage (search, create) Wizard for all types of metadata """
    widgets: dict = {}

    templates = {
        "initial": "aristotle_mdr/create/concept_wizard_1_search.html",
        "results": "aristotle_mdr/create/concept_wizard_2_results.html",
    }
    template_name = "aristotle_mdr/create/concept_wizard_wrapper.html"
    form_list = [
        ("initial", MDRForms.wizards.Concept_1_Search),
        ("results", MDRForms.wizards.Concept_2_Results),
    ]

    additional_records_active = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots_active = is_active_module('aristotle_mdr.contrib.slots')

    def get_form(self, step=None, data=None, files=None):
        if step is None:  # pragma: no cover
            step = self.steps.current
        if step == "results":
            similar = self.find_similar()
            duplicates = self.find_duplicates()
            kwargs = self.get_form_kwargs(step)
            kwargs.update({
                'custom_fields': CustomField.objects.get_for_model(self.model, user=self.request.user),
                'data': data,
                'files': files,
                'prefix': self.get_form_prefix(step, self.form_list[step]),
                'initial': self.get_cleaned_data_for_step('initial'),
                'check_similar': len(similar) > 0 or len(duplicates) > 0
            })
            return MDRForms.wizards.subclassed_wizard_2_Results(self.model)(**kwargs)
        return super().get_form(step, data, files)

    def get_extra_formsets(self, item=None, postdata=None, clone_item=False):
        extra_formsets = super().get_extra_formsets(item, postdata)

        if self.slots_active:
            slots_formset = self.get_slots_formset()(
                queryset=Slot.objects.none(),
                data=postdata
            )
            extra_formsets.append({
                'formset': slots_formset,
                'title': 'Slots',
                'type': 'slot',
                'saveargs': None
            })

        recordrelation_formset = self.get_recordrelations_formset()(
            data=postdata
        )
        # Override the queryset to restrict to the records the user has permission to view
        for record_relation_form in recordrelation_formset:
            record_relation_form.fields['organization_record'].queryset = MDR.OrganizationRecord.objects.visible(
                self.request.user).order_by('name')

        extra_formsets.append({
            'formset': recordrelation_formset,
            'title': 'Record Relation',
            'type': 'record_relation',
            'saveargs': None
        })

        return extra_formsets

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        if self.steps.current == 'initial':
            context['step_title'] = _('Search for existing content')

        if self.steps.current == 'results':
            self.search_terms = self.get_cleaned_data_for_step('initial')
            context.update({'search_name': self.search_terms['name'], })
            duplicates = self.find_duplicates()
            if duplicates:
                context.update({'duplicate_items': duplicates})
            else:
                context.update({'similar_items': self.find_similar()})
            context['step_title'] = _('Select or create')

            slots_active = is_active_module('aristotle_mdr.contrib.slots')
            context['slots_active'] = slots_active
            context['show_slots_tab'] = slots_active or form.custom_fields

            if 'extra_formsets' in kwargs:
                fslist = kwargs['extra_formsets']
            else:
                fslist = self.get_extra_formsets(item=self.model)

            fscontext = self.get_formset_context(fslist)
            context.update(fscontext)

        context.update({'model_name': self.model._meta.verbose_name,
                        'model_name_plural': self.model._meta.verbose_name_plural.title,
                        'help': ConceptHelp.objects.filter(
                            app_label=self.model._meta.app_label,
                            concept_type=self.model._meta.model_name
                        ).first(),
                        'model_class': self.model,
                        'template_name': self.template_name,
                        'current_step': self.steps.current,
                        'additional_records_active': self.additional_records_active
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

    def get(self, *args, **kwargs):
        if 'results_postdata' in self.request.session.keys():
            self.request.session.pop('results_postdata')
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        if self.steps.current == 'results':
            extra_formsets = self.get_extra_formsets(item=self.model, postdata=self.request.POST)

            formsets_invalid = self.validate_formsets(extra_formsets)
            if formsets_invalid:
                form = self.get_form(data=self.request.POST, files=self.request.FILES)
                return self.render(form=form, extra_formsets=extra_formsets)
            else:
                self.request.session['results_postdata'] = self.request.POST

        return super().post(*args, **kwargs)

    @transaction.atomic()
    def done(self, form_list, **kwargs):
        saved_item = None

        for form in form_list:
            saved_item = form.save(commit=False)
            if saved_item is not None:
                saved_item.submitter = self.request.user
                saved_item.save()

                with reversion.create_revision():
                    reversion.set_user(self.request.user)
                    reversion.set_comment("Added via concept wizard")

                    form.save_custom_fields(saved_item)
                    form.save_m2m()

                    if 'results_postdata' in self.request.session:
                        extra_formsets = self.get_extra_formsets(item=self.model,
                                                                 postdata=self.request.session['results_postdata'])
                        formsets_invalid = self.validate_formsets(extra_formsets)
                        if not formsets_invalid:
                            final_formsets = []
                            for info in extra_formsets:
                                if info['saveargs'] is not None:
                                    info['saveargs']['item'] = saved_item
                                else:
                                    info['formset'].instance = saved_item
                                final_formsets.append(info)

                            self.save_formsets(final_formsets)
                        self.request.session.pop('results_postdata')

                    saved_item.save()

        return HttpResponseRedirect(url_slugify_concept(saved_item))

    def find_duplicates(self):
        if hasattr(self, 'duplicate_items'):
            return self.duplicate_items
        self.search_terms = self.get_cleaned_data_for_step('initial')
        name = self.search_terms['name']
        name = name.strip()
        self.duplicate_items = self.model.objects.filter(name__iexact=name).public().all()
        return self.duplicate_items

    def find_similar(self, model=None):
        """Looks for items of a given item type with the given search terms"""
        from aristotle_mdr.forms.search import get_permission_sqs as PSQS, EmptyPermissionSearchQuerySet

        if hasattr(self, 'similar_items'):
            return self.similar_items

        self.search_terms = self.get_cleaned_data_for_step('initial')

        if model is None:
            model = self.model

        query = self.search_terms['definition'] + " " + self.search_terms['name']
        if query == " ":
            return EmptyPermissionSearchQuerySet()

        similar = PSQS().models(model).auto_query(query)\
            .apply_permission_checks(user=self.request.user)\
            .filter(statuses__in=[int(s) for s in [MDR.STATES.standard, MDR.STATES.preferred]])[:10]

        self.similar_items = similar

        return self.similar_items


def no_valid_property(wizard):
    return not wizard.get_property()


def no_valid_object_class(wizard):
    return not wizard.get_object_class()


def no_valid_value_domain(wizard):
    return not wizard.get_value_domain()


class MultiStepAristotleWizard(PermissionWizard):
    """
    This is the base wizard for Data Element and Data Element Concepts only.
    We can reuse a lot of the functionality as DE and DECs have a lot of the same underlying components.
    This should not be extended for creating other type of Aristotle/11179 concepts - make a fresh wizard.
    """

    @property
    def display(self):
        return self.__doc__

    def get_object_class(self):
        if hasattr(self, '_object_class'):
            return self._object_class
        else:
            ocp = self.get_cleaned_data_for_step('component_results')
            if ocp:
                oc = ocp.get('oc_options', None)
                if oc:
                    self._object_class = oc
                    return self._object_class
        return None

    def get_property(self):
        if hasattr(self, '_property'):
            return self._property
        else:
            ocp = self.get_cleaned_data_for_step('component_results')
            if ocp:
                pr = ocp.get('pr_options', None)
                if pr:
                    self._property = pr
                    return self._property
        return None

    def get_value_domain(self):
        if hasattr(self, '_valuedomain'):
            return self._valuedomain
        else:
            ocp = self.get_cleaned_data_for_step('component_results')
            if ocp:
                pr = ocp.get('vd_options', None)
                if pr:
                    self._valuedomain = pr
                    return self._valuedomain
        return None

    def find_similar(self, name, definition, model=None):
        """Looks for items of a given item type with the given search terms"""
        from aristotle_mdr.forms.search import get_permission_sqs as PSQS
        if model is None:
            model = self.model
        if not hasattr(self, "similar_items"):
            self.similar_items = {}
        cached_items = self.similar_items.get(model, None)
        if cached_items:
            return cached_items

        # Limit results to 10, as more than this tends to slow down everything.
        # If a user is getting more than 10 results they probably haven't named things properly
        similar = PSQS().models(model).auto_query(name + " " + definition).apply_permission_checks(user=self.request.user)[:10]
        self.similar_items[model] = similar
        return similar

    def get_field_defaults(self, field_prefix):
        ocp = self.get_cleaned_data_for_step('component_search')
        fd = {}
        if ocp:
            fd = {
                'name': ocp.get(field_prefix + '_name', ""),
                'definition': ocp.get(field_prefix + '_desc', "")
            }
        return fd

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if step is None:  # pragma: no cover
            step = self.steps.current
        if step == "make_oc":
            initial.update(self.get_field_defaults('oc'))
        elif step == "make_p":
            initial.update(self.get_field_defaults('pr'))
        elif step in ['find_dec_results', 'make_dec']:  # Account for DE and DEC wizards
            made_oc = self.get_cleaned_data_for_step('make_oc')
            if self.get_object_class():
                oc_name = self.get_object_class().name
                oc_desc = self.get_object_class().definition
            elif made_oc:
                oc_name = made_oc.get('name', _("No object class name found"))
                oc_desc = made_oc.get('definition', _("No object class definition found"))
            else:
                oc_name = _("No object class name found")
                oc_desc = _("No object class definition found")
            oc_desc = make_it_clean(oc_desc)
            if oc_desc:
                # lower case the first letter as this will be the latter part of a sentence
                oc_desc = oc_desc[0].lower() + oc_desc[1:]

            made_pr = self.get_cleaned_data_for_step('make_p')
            if self.get_property():
                pr_name = self.get_property().name
                pr_desc = self.get_property().definition
            elif made_pr:
                pr_name = made_pr.get('name', _("No property name found"))
                pr_desc = made_pr.get('definition', _("No property definition found"))
            else:
                pr_name = _("No property name found")
                pr_desc = _("No property definition found")
            pr_desc = make_it_clean(pr_desc)
            if pr_desc and pr_desc[-1] == ".":
                # remove the tailing period as we are going to try to make a sentence
                pr_desc = pr_desc[:-1]

            SEPARATORS = fetch_aristotle_settings().get('SEPARATORS', {})
            initial.update({
                'name': u"{oc}{separator}{pr}".format(
                    oc=oc_name,
                    separator=SEPARATORS["DataElementConcept"],
                    pr=pr_name,
                ),
                'definition': _(u"<p>{pr} of {oc}</p> - This was an autogenerated definition.").format(
                    oc=oc_desc, pr=pr_desc
                )
            })
        return initial

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['show_slots_tab'] = False
        return context


class DataElementConceptWizard(MultiStepAristotleWizard):
    __doc__ = _(
        "This wizard steps a user through creating a Data Element Concept, "
        "by reusing or creating the component parts required "
        "- an Object Class and a Property."
    )

    model = MDR.DataElementConcept
    templates = {
        "component_search": "aristotle_mdr/create/dec_1_initial_search.html",
        "component_results": "aristotle_mdr/create/dec_2_search_results.html",
        "make_oc": "aristotle_mdr/create/concept_wizard_2_results.html",
        "make_p": "aristotle_mdr/create/concept_wizard_2_results.html",
        "find_dec_results": "aristotle_mdr/create/dec_3_dec_search_results.html",
        "completed": "aristotle_mdr/create/dec_4_complete.html",
        }
    template_name = "aristotle_mdr/create/dec_template_wrapper.html"
    form_list = [
        ("component_search", MDRForms.wizards.DEC_OCP_Search),
        ("component_results", MDRForms.wizards.DEC_OCP_Results),
        ("make_oc", MDRForms.wizards.subclassed_wizard_2_Results(MDR.ObjectClass)),
        ("make_p", MDRForms.wizards.subclassed_wizard_2_Results(MDR.Property)),
        ("find_dec_results", MDRForms.wizards.DEC_Find_DEC_Results),
        ("completed", MDRForms.wizards.DEC_Complete),
    ]
    condition_dict = {
        "make_oc": no_valid_object_class,
        "make_p": no_valid_property,
        }

    def get_data_element_concept(self):
        if hasattr(self, '_data_element_concept'):
            return self._data_element_concept

        oc = self.get_object_class()
        pr = self.get_property()

        if oc and pr:
            self._data_element_concept = MDR.DataElementConcept.objects.filter(objectClass=oc, property=pr).visible(self.request.user).order_by('-created')[:10]
            return self._data_element_concept
        else:
            return []

    def get_form_kwargs(self, step):
        # determine the step if not given
        if step is None:  # pragma: no cover
            step = self.steps.current
        kwargs = super().get_form_kwargs(step)

        if step == 'component_results':
            ocp = self.get_cleaned_data_for_step('component_search')
            if ocp:
                kwargs.update({
                    'oc_similar': self.find_similar(
                        model=MDR.ObjectClass,
                        name=ocp.get('oc_name', ""),
                        definition=ocp.get('oc_desc', "")
                    ),
                    'pr_similar': self.find_similar(
                        model=MDR.Property,
                        name=ocp.get('pr_name', ""),
                        definition=ocp.get('pr_desc', "")
                    )
                })
        elif step in ['make_oc', 'make_p']:
            kwargs.update({
                'check_similar': False  # They waived this on the previous page
            })
        elif step == 'find_dec_results':
            kwargs.update({
                'check_similar': self.get_data_element_concept()
                })
        return kwargs

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        context.update({
            'component_search': {'percent_complete': 20, 'step_title': _('Search for components')},
            'component_results': {'percent_complete': 40, 'step_title': _('Refine components')},
            'make_oc': {'percent_complete': 50, 'step_title': _('Create Object Class')},
            'make_p': {'percent_complete': 60, 'step_title': _('Create Property')},
            'find_dec_results': {'percent_complete': 80, 'step_title': _('Review Data Element Concept')},
            'completed': {'percent_complete': 100, 'step_title': _('Complete and Save')},
            }.get(self.steps.current, {}))

        if self.steps.current == 'component_results':
            ocp = self.get_cleaned_data_for_step('component_search')
            context.update({
                'oc_name': ocp.get('oc_name', ""),
                'oc_definition': ocp.get('oc_desc', ""),
                'pr_name': ocp.get('pr_name', ""),
                'pr_definition': ocp.get('pr_desc', ""),
            })
        if self.steps.current == 'make_oc':
            context.update({
                'model_name': MDR.ObjectClass._meta.verbose_name,
                'model_class': MDR.ObjectClass,
                })
        if self.steps.current == 'make_p':
            context.update({
                'model_name': MDR.Property._meta.verbose_name,
                'model_class': MDR.Property,
                })
        if self.steps.current == 'find_dec_results':
            context.update({
                'oc_match': self.get_object_class(),
                'pr_match': self.get_property(),
                'model_class': MDR.DataElementConcept,
                'dec_matches': self.get_data_element_concept(),
                'hide_components_tab': True
                })
        if self.steps.current == 'completed':
            context.update({
                'dec_matches': self.get_data_element_concept(),
                'oc': self.get_object_class() or self.get_cleaned_data_for_step('make_oc'),
                'pr': self.get_property() or self.get_cleaned_data_for_step('make_p'),
                'made_oc': self.get_cleaned_data_for_step('make_oc'),
                'made_pr': self.get_cleaned_data_for_step('make_p'),
                'made_dec': self.get_cleaned_data_for_step('find_dec_results'),
                })
        context.update({
            'template_name': self.template_name,
            })
        return context

    @reversion.create_revision()
    def done(self, form_list, **kwargs):
        reversion.set_user(self.request.user)
        reversion.set_comment("Added via data element concept wizard")

        oc = self.get_object_class()
        pr = self.get_property()
        dec = None
        for form in form_list:
            saved_item = form.save(commit=False)
            if saved_item is not None:
                saved_item.submitter = self.request.user
                saved_item.save()
            if type(saved_item) == MDR.Property:
                pr = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Property '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.ObjectClass:
                oc = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Object Class '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.DataElementConcept:
                dec = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Data Element Concept '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
        if dec is not None:
            dec.objectClass = oc
            dec.property = pr
            dec.save()
        return HttpResponseRedirect(url_slugify_concept(dec))


def no_valid_data_element_concept(wizard):
    return not wizard.get_data_element_concept()


def has_valid_data_element_concepts(wizard):
    return wizard.get_data_element_concepts()


def has_valid_data_elements_from_components(wizard):
    return wizard.get_data_elements_from_components()


class DataElementWizard(MultiStepAristotleWizard):
    __doc__ = _(
        "This wizard steps a user through creating a Data Element, "
        "by reusing or creating all the components of the Data Element, "
        "the Value Domain and the Data Element Concept, which is broken down "
        "further as an Object Class and Property."
    )

    model = MDR.DataElement
    template_name = "aristotle_mdr/create/de_template_wrapper.html"
    templates = {
        "component_search": "aristotle_mdr/create/de_1_initial_search.html",
        "component_results": "aristotle_mdr/create/de_2_search_results.html",
        "make_oc": "aristotle_mdr/create/concept_wizard_2_results.html",
        "make_p": "aristotle_mdr/create/concept_wizard_2_results.html",
        "find_de_from_comp": "aristotle_mdr/create/de_3_de_search_results_from_components.html",
        "find_dec_results": "aristotle_mdr/create/de_3_dec_search_results.html",
        "make_dec": "aristotle_mdr/create/de_4_dec_create.html",
        "make_vd": "aristotle_mdr/create/concept_wizard_2_results.html",
        "find_de_results": "aristotle_mdr/create/de_4_de_search_results.html",
        "completed": "aristotle_mdr/create/de_6_complete.html",
        }
    form_list = [
        ("component_search", MDRForms.wizards.DE_OCPVD_Search),
        ("component_results", MDRForms.wizards.DE_OCPVD_Results),
        ("make_oc", MDRForms.wizards.subclassed_wizard_2_Results(MDR.ObjectClass)),
        ("make_p", MDRForms.wizards.subclassed_wizard_2_Results(MDR.Property)),
        ("find_de_from_comp", MDRForms.wizards.DE_Find_DE_Results_from_components),
        ("find_dec_results", MDRForms.wizards.DE_Find_DEC_Results),
        ("make_dec", MDRForms.wizards.subclassed_wizard_2_Results(MDR.DataElementConcept)),
        ("make_vd", MDRForms.wizards.subclassed_wizard_2_Results(MDR.ValueDomain)),
        ("find_de_results", MDRForms.wizards.DE_Find_DE_Results),
        ("completed", MDRForms.wizards.DE_Complete),
    ]
    condition_dict = {
        "make_oc": no_valid_object_class,
        "make_p": no_valid_property,
        "find_de_from_comp": has_valid_data_elements_from_components,
        "find_dec_results": has_valid_data_element_concepts,
        "make_dec": no_valid_data_element_concept,
        "make_vd": no_valid_value_domain,
    }

    def get_data_element_concepts(self):
        if hasattr(self, '_data_element_concepts'):
            return self._data_element_concepts
        oc = self.get_object_class()
        pr = self.get_property()
        if oc and pr:
            self._data_element_concepts = MDR.DataElementConcept.objects.filter(objectClass=oc, property=pr).visible(self.request.user)
            return self._data_element_concepts
        else:
            return []

    def get_data_element_concept(self):
        if hasattr(self, '_data_element_concept'):
            return self._data_element_concept
        else:
            results = self.get_cleaned_data_for_step('find_dec_results')
            if results:
                dec = results.get('dec_options', None)
                if dec:
                    self._data_element_concept = dec
                    return self._data_element_concept
        return None

    def get_data_elements_from_components(self):
        if hasattr(self, '_data_element_from_components'):
            return self._data_element_from_components
        # dec = self.get_data_element_concepts()
        oc = self.get_object_class()
        pr = self.get_property()
        vd = self.get_value_domain()
        if oc and pr and vd:
            self._data_element_from_components = MDR.DataElement.objects.filter(
                dataElementConcept__objectClass=oc,
                dataElementConcept__property=pr,
                valueDomain=vd
                ).visible(self.request.user)

            return self._data_element_from_components
        else:
            return []

    def get_data_element(self):
        if hasattr(self, '_data_element'):
            return self._data_element
        else:
            results = self.get_cleaned_data_for_step('find_de_results')
            if results:
                de = results.get('dec_options', None)
                if de:
                    self._data_element = de
                    return self._data_element
        return None

    def get_data_elements(self):
        if hasattr(self, '_data_elements'):
            return self._data_elements
        dec = self.get_data_element_concept()
        results = self.get_cleaned_data_for_step('find_dec_results')
        if results:
            dec = results.get('dec_options', None)
        vd = self.get_value_domain()
        if dec and vd:
            self._data_elements = MDR.DataElement.objects.filter(dataElementConcept=dec, valueDomain=vd).visible(self.request.user).order_by('-created')[:10]
            return self._data_elements
        else:
            return []

    def get_form_kwargs(self, step):
        # determine the step if not given
        kwargs = super().get_form_kwargs(step)
        if step is None:  # pragma: no cover
            step = self.steps.current

        if step == 'component_results':
            ocp = self.get_cleaned_data_for_step('component_search')
            if ocp:
                kwargs.update({
                    'oc_similar': self.find_similar(
                        model=MDR.ObjectClass,
                        name=ocp.get('oc_name', ""),
                        definition=ocp.get('oc_desc', "")
                    ),
                    'pr_similar': self.find_similar(
                        model=MDR.Property,
                        name=ocp.get('pr_name', ""),
                        definition=ocp.get('pr_desc', "")
                    ),
                    'vd_similar': self.find_similar(
                        model=MDR.ValueDomain,
                        name=ocp.get('vd_name', ""),
                        definition=ocp.get('vd_desc', "")
                    )
                })
        elif step in ['make_oc', 'make_p', 'make_vd', 'make_dec']:
            kwargs.update({
                'check_similar': False  # They waived this on a previous page
            })
        elif step == 'find_dec_results':
            kwargs.update({
                'dec_similar': self.get_data_element_concepts()
                })
        elif step == 'find_de_results':
            kwargs.update({
                'check_similar': self.get_data_elements()
                })

        return kwargs

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        context.update({
            'template_name': self.template_name,
            'next_button_text': _("Next")
            })

        context.update({
            'component_search': {
                'percent_complete': 10,
                'step_title': _('Search for components'),
                'next_button_text': _("Search"),
            },
            'component_results': {'percent_complete': 20, 'step_title': _('Refine components')},
            'find_de_from_comp': {'percent_complete': 30, 'step_title': _('Review Data Element')},
            'make_oc': {
                'percent_complete': 40,
                'step_title': _('Create Object Class'),
                'next_button_text': _("Save Object Class"),
                },
            'make_p': {
                'percent_complete': 50,
                'step_title': _('Create Property'),
                'next_button_text': _("Save Property"),
            },
            'find_dec_results': {'percent_complete': 60, 'step_title': _('Select Data Element Concept')},
            'make_dec': {
                'percent_complete': 70,
                'step_title': _('Create Data Element Concept'),
                'next_button_text': _("Save Data Element Concept"),
            },
            'make_vd': {
                'percent_complete': 80,
                'step_title': _('Create Value Domain')
            },
            'find_de_results': {'percent_complete': 90, 'step_title': _('Review Data Element')},
            'completed': {
                'percent_complete': 100,
                'step_title': _('Complete and Save'),
                'next_button_text': _("Save and Finish"),
            },
            }.get(self.steps.current, {}))

        # Order of the steps make oc make p
        if self.steps.current == 'component_results':
            ocp = self.get_cleaned_data_for_step('component_search')
            context.update({
                'oc_name': ocp.get('oc_name', ""),
                'oc_definition': ocp.get('oc_desc', ""),
                'pr_name': ocp.get('pr_name', ""),
                'pr_definition': ocp.get('pr_desc', ""),
                'vd_name': ocp.get('vd_name', ""),
                'vd_definition': ocp.get('vd_desc', "")
            })

        if self.steps.current == "make_oc":
            context.update({
                'model_name': MDR.ObjectClass._meta.verbose_name,
                'model_class': MDR.ObjectClass,
                })

        if self.steps.current == "make_p":
            context.update({
                'model_name': MDR.Property._meta.verbose_name,
                'model_class': MDR.Property
            })

        if self.steps.current == 'make_vd':
            context.update({
                'model_name': MDR.ValueDomain._meta.verbose_name,
                'model_class': MDR.ValueDomain,
                })
        if self.steps.current == 'make_dec':
            context.update({
                'model_class': MDR.DataElementConcept,
            })
        if self.steps.current == 'find_dec_results':
            context.update({
                'oc_match': self.get_object_class(),
                'pr_match': self.get_property(),
                'model_class': MDR.DataElementConcept,
                'dec_matches': self.get_data_element_concepts(),
                'hide_components_tab': True
                })
        if self.steps.current == 'find_de_from_comp':
            context.update({
                'oc_match': self.get_object_class(),
                'pr_match': self.get_property(),
                'vd_match': self.get_value_domain(),
                'model_class': MDR.DataElement,
                'de_matches': self.get_data_elements_from_components()
                })
        if self.steps.current == 'find_de_results':
            context.update({
                'dec_match': self.get_data_element_concept(),
                'vd_match': self.get_value_domain(),
                'de_matches': self.get_data_elements(),
                'model_class': MDR.DataElement,
                'hide_components_tab': True
                })
        if self.steps.current == 'completed':
            context.update({
                'oc': self.get_object_class() or self.get_cleaned_data_for_step('make_oc'),
                'pr': self.get_property() or self.get_cleaned_data_for_step('make_p'),
                'vd': self.get_value_domain() or self.get_cleaned_data_for_step('make_vd'),
                'dec': self.get_data_element_concept() or self.get_cleaned_data_for_step('make_dec'),
                'made_oc': self.get_cleaned_data_for_step('make_oc'),
                'made_pr': self.get_cleaned_data_for_step('make_p'),
                'made_vd': self.get_cleaned_data_for_step('make_vd'),
                'made_dec': self.get_cleaned_data_for_step('make_dec'),
                'de_matches': self.get_data_elements(),
                'made_de': self.get_cleaned_data_for_step('find_de_results'),
                })
        return context

    def get_form_initial(self, step):
        initial = super().get_form_initial(step)
        if step is None:  # pragma: no cover
            step = self.steps.current
        if step == "make_vd":
            initial.update(self.get_field_defaults('vd'))
        elif step == 'find_de_results':
            made_vd = self.get_cleaned_data_for_step('make_vd')
            if self.get_value_domain():
                vd_name = self.get_value_domain().name
                vd_desc = self.get_value_domain().definition
            elif made_vd:
                vd_name = made_vd.get('name', _("No value domain name found"))
                vd_desc = made_vd.get('definition', _("No value domain definition found"))
            else:
                vd_name = _("No value domain name found")
                vd_desc = _("No value domain definition found")
            vd_desc = make_it_clean(vd_desc)
            if vd_desc:
                # lower case the first letter as this will be the latter part of a sentence
                vd_desc = vd_desc[0].lower() + vd_desc[1:]

            made_dec = self.get_cleaned_data_for_step('make_dec')
            if self.get_data_element_concept():
                dec_name = self.get_data_element_concept().name
                dec_desc = self.get_data_element_concept().definition
            elif made_dec:
                dec_name = made_dec.get('name', _("No property name found"))
                dec_desc = made_dec.get('definition', _("No property definition found"))
            else:
                dec_name = _("No property name found")
                dec_desc = _("No property definition found")
            dec_desc = make_it_clean(dec_desc)

            if dec_desc and dec_desc[-1] == ".":
                # remove the trailing period as we are going to try to make a sentence
                dec_desc = dec_desc[:-1]

            SEPARATORS = fetch_aristotle_settings().get('SEPARATORS', {})

            initial.update({
                'name': u"{dec}{separator}{vd}".format(dec=dec_name, separator=SEPARATORS["DataElement"], vd=vd_name),
                'definition': _(u"<p>{dec}, recorded as {vd}</p> - This was an autogenerated definition.").format(
                    dec=dec_desc, vd=vd_desc
                    )
                })
        return initial

    @reversion.create_revision()
    def done(self, form_list, **kwargs):
        reversion.set_user(self.request.user)
        reversion.set_comment("Added via data element wizard")

        oc = self.get_object_class()
        pr = self.get_property()
        vd = self.get_value_domain()
        dec = self.get_data_element_concept()
        de = None
        for form in form_list:
            saved_item = form.save(commit=False)
            if saved_item is not None:
                saved_item.submitter = self.request.user
                saved_item.save()
            if type(saved_item) == MDR.Property:
                pr = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Property '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.ObjectClass:
                oc = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Object Class '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.DataElementConcept:
                dec = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Data Element Concept '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.ValueDomain:
                vd = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New ValueDomain '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
            if type(saved_item) == MDR.DataElement:
                de = saved_item
                messages.success(
                    self.request,
                    mark_safe(_("New Data Element '{name}' Saved - <a href='{url}'>id:{id}</a>").format(
                        url=url_slugify_concept(saved_item),
                        name=saved_item.name, id=saved_item.id
                    ))
                )
        if dec is not None:
            dec.objectClass = oc
            dec.property = pr
            dec.save()
        if de is not None:
            de.dataElementConcept = dec
            de.valueDomain = vd
            de.save()
        return HttpResponseRedirect(url_slugify_concept(de))
