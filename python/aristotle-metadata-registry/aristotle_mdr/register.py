"""
Aristotle-MDR concept register
------------------------------

This module allows developers to easily register new concept models with the core
functionality of Aristotle-MDR. The ``register_concept`` is a wrapper around three
methods that registers a new concept with the Django-Admin site, with the
Django-Autocomplete and with a class for a Haystack search index. This is all done
in a way that conforms to the permissions required for control item visibility.

Other methods in this module can be called, to highly customise how concepts are
used within the admin site and search, but should be considered internal methods
and future releases of Aristotle-MDR may break code that uses these methods.
"""

from django.conf import settings
from django.contrib import admin
from django.utils.module_loading import import_string
from django.utils.translation import ugettext_lazy as _

from aristotle_mdr.search_indexes import ConceptIndex
from aristotle_mdr.models import _concept
import aristotle_mdr.search_indexes as search_index

from haystack import connections
from haystack.constants import DEFAULT_ALIAS
from haystack import indexes

import logging
logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


def register_concept(concept_class, *args, **kwargs):
    """
    A handler for third-party apps to make registering extension models based on `aristotle_mdr.models.concept` easier.

    Sets up the version controls, search indexes, django administrator page
    and autocomplete handlers.
    All `args` and `kwargs` are passed to the called methods. For examples of
    what can be passed into this method review the other methods in
    `aristotle_mdr.register`.

    Example usage (based on the models in the extensions test suite):

        register_concept(Question, extra_fieldsets=[('Question','question_text'),]
    """

    register_concept_reversions(concept_class, *args, **kwargs)  # must come before admin
    register_concept_admin(concept_class, *args, **kwargs)
    register_concept_search_index(concept_class, *args, **kwargs)


def register_concept_reversions(concept_class, *args, **kwargs):
    """
    Registers the concept with reversion
    :param concept_class:
    :param args:
    :param kwargs:
    """
    from reversion import revisions as reversion

    follows = kwargs.get('reversion', {}).get('follow', [])
    reversion.register(concept_class, follow=follows, format='aristotle_mdr_json_uuid_compatible')

    follow_classes = kwargs.get('reversion', {}).get('follow_classes', [])
    for cls in follow_classes:
        reversion.register(cls)

    if reversion.is_registered(_concept):
        reversion.unregister(_concept)


def register_concept_search_index(concept_class, *args, **kwargs):
    """
    Registers the given `concept` with a Haystack search index that conforms
    to Aristotle permissions. If the concept to be registered does not have a
    template for serving a search document, a basic document with just the basic
    fields from `aristotle_mdr.models._concept` will be used when indexing items.

    :param concept concept_class: The model that is to be registered for searching.
    """
    search_category = kwargs.get('search_category', None)
    class_name = "%s_%sSearchIndex" % (concept_class._meta.app_label, concept_class.__name__)
    model_index = kwargs.get('custom_search_index', create(concept_class, search_category))
    setattr(search_index, class_name, model_index)

    search_index.registered_indexes.append(model_index)

    # Since we've added a new class, kill the index so it is rebuilt.
    connections[DEFAULT_ALIAS]._index = None


def create(cls, set_search_category=None):
    if hasattr(settings, 'HAYSTACK_BASE_INDEX_CLASS'):
        base_index_class = import_string(settings.HAYSTACK_BASE_INDEX_CLASS)
    else:
        base_index_class = ConceptIndex

    class SubclassedConceptIndex(base_index_class, indexes.Indexable):
        if set_search_category is not None:
            search_category = set_search_category

        def get_model(self):
            return cls
    return SubclassedConceptIndex


def register_concept_admin(concept_class, *args, **kwargs):
    """Registers the given ``concept`` with the Django admin backend based on the default
    ``aristotle_mdr.admin.ConceptAdmin``.
    Additional parameters are only required if a model has additional fields or
    references to other models.
    :param boolean auto_fieldsets: If no extra_fieldsets, when set to true this generates a list of fields for the admin page as "Extra fields for [class]"
    :param concept concept_class: The model that is to be registered
    :param list extra_fieldsets: Model-specific `fieldsets <https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.ModelAdmin.fieldsets>`_ to be displayed. Fields in the tuples given should be those *not* defined by the base ``aristotle_mdr.models._concept`` class.
    :param list extra_inlines: Model-specific `inline <https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.ModelAdmin.inlines>`_ admin forms to be displayed.
    """
    extra_fieldsets = kwargs.get('extra_fieldsets', [])
    auto_fieldsets = kwargs.get('auto_fieldsets', False)
    extra_inlines = kwargs.get('extra_inlines', [])
    extra_name_suggest_fields = kwargs.get('name_suggest_fields', [])

    # late import this as we call this in aristotle_mdr.admin and need it to be ready before we call this.
    from aristotle_mdr.admin import ConceptAdmin
    from aristotle_mdr.models import concept
    if not extra_fieldsets and auto_fieldsets:
        # returns every field that isn't in a concept
        field_names = [f.name for f in concept._meta.get_fields()] + ['supersedes']
        m2ms = [
            f for f in concept_class._meta.get_fields()
            if f.many_to_many and not f.auto_created
        ]
        m2m_rel = [
            f.related_model
            for f in concept_class._meta.get_fields()
            if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete
        ]
        auto_fieldset = []
        auto_inlines = []
        for f in concept_class._meta.get_fields():
            if f.name not in field_names and f.name not in concept_class.admin_page_excludes:
                auto_fieldset.append(f.name)

        if auto_fieldset:
            extra_fieldsets_name = _('Extra fields for %(class_name)s') % {'class_name': concept_class._meta.verbose_name.title()}
            extra_fieldsets = [(extra_fieldsets_name, {'fields': auto_fieldset})]
        for inline_field in auto_inlines:
            class AutoInline(admin.TabularInline):
                model = inline_field.related_model
                extra = 0
            extra_inlines.append(AutoInline)

    class SubclassedConceptAdmin(ConceptAdmin):
        model = concept_class
        if extra_name_suggest_fields:
            name_suggest_fields = extra_name_suggest_fields
        fieldsets = ConceptAdmin.fieldsets + extra_fieldsets
        inlines = ConceptAdmin.inlines + extra_inlines

    admin.site.register(concept_class, SubclassedConceptAdmin)
