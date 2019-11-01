from typing import List, Dict, Tuple
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.core.exceptions import ImproperlyConfigured
from django.forms import model_to_dict
from django.template.defaultfilters import slugify
from django.utils.encoding import force_text
from django.utils.module_loading import import_string
from django.utils.text import get_text_list
from django.utils.translation import ugettext as _
from django.db.models import Model
from django.contrib.contenttypes.models import ContentType

import bleach
import logging
import re
from pypandoc import _ensure_pandoc_path

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)


class classproperty(object):

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


def concept_to_dict(obj):
    """
    A replacement for the ```django.form.model_to_dict`` that includes additional
    ``ManyToManyFields``, but removes certain concept fields.
    """

    excluded_fields = [
        '_concept_ptr',
        'version',
        'workgroup',
        'pk',
        'id',
        'supersedes',
        'superseded_by',
        '_is_public',
        '_is_locked',
        '_type',
    ]

    concept_dict = model_to_dict(
        obj,
        fields=[field.name for field in obj._meta.fields if field.name not in excluded_fields],
        exclude=excluded_fields
    )
    return concept_dict


def concept_to_clone_dict(obj):
    """
    An extension of ``aristotle_mdr.utils.concept_to_dict`` that adds a 'clone'
    suffix to the name when cloning an item.
    """

    from django.utils.translation import ugettext  # Do at run time because reasons
    clone_dict = concept_to_dict(obj)
    # Translators: The '(clone)' prefix is a noun, indicating an object is a clone of another - for example "Person-Sex" compared to "Person-Sex (clone)"
    clone_dict['name'] = clone_dict['name'] + ugettext(u" (clone)")
    return clone_dict


def get_download_template_path_for_item(item, template_type, subpath=''):
    app_label = item._meta.app_label
    model_name = item._meta.model_name
    if subpath:
        template = "%s/downloads/%s/%s/%s.html" % (app_label, template_type, subpath, model_name)
    else:
        template = "%s/downloads/%s/%s.html" % (app_label, template_type, model_name)

    from django.template.loader import get_template
    from django.template import TemplateDoesNotExist
    try:
        get_template(template)
    except TemplateDoesNotExist:
        # This is ok. If a template doesn't exists pass a default one
        # Maybe in future log an error?
        template = "%s/downloads/%s/%s/%s.html" % ("aristotle_mdr", template_type, subpath, "managedContent")
    return template


def url_slugify_concept(item):
    item_model = item.item_type.model_class()
    slug = slugify(item.name)[:50]
    if not slug:
        slug = "--"
    return reverse(
        "aristotle:item",
        kwargs={'iid': item.pk, 'model_slug': item_model._meta.model_name, 'name_slug': slug}
    )


def url_slugify_workgroup(workgroup):
    slug = slugify(workgroup.name)[:50]
    if not slug:
        slug = "--"
    return reverse(
        "aristotle:workgroup",
        kwargs={'iid': workgroup.pk, 'name_slug': slug}
    )


def url_slugify_registration_authoritity(ra):
    slug = slugify(ra.name)[:50]
    if not slug:
        slug = "--"
    return reverse(
        "aristotle:registrationAuthority",
        kwargs={'iid': ra.pk, 'name_slug': slug}
    )


def url_slugify_organization(org):
    slug = slugify(org.name)[:50]
    if not slug:
        slug = "--"
    return reverse(
        "aristotle:organization",
        kwargs={'iid': org.pk, 'name_slug': slug}
    )


def url_slugify_issue(issue):
    return reverse(
        "aristotle_issues:issue",
        kwargs={'iid': issue.item.pk, 'pk': issue.pk}
    )


def construct_change_message_for_form(form, model=None):
    """
    This function returns the string representation of fields that have been modified in a form.
    Particularly useful in form_valid() functions to generate messages and comments.
    :param form: Form to evaluate the fields that have been modified.
    :param model: Model (optional). If this parameter is included, the list returned will contain only the verbose name
    version of the model field names.
    :return: String. Description of the modified fields of a form.
    """
    change_message = ""
    if form and form.changed_data:
        changed_fields = form.changed_data
        if 'last_fetched' in changed_fields:
            changed_fields.remove('last_fetched')

        if model:
            model_field_names = set()
            for model_field in model._meta.fields:
                model_field_names.add(model_field.name)

            for i, changed_field in enumerate(changed_fields):
                if changed_field in model_field_names:
                    changed_fields[i] = model._meta.get_field(changed_field).verbose_name
        change_message = _('Changed %s.') % get_text_list(changed_fields, _('and'))

    return change_message


def construct_change_message(form, formsets):
    """
    This function constructs messages for new, changed or deleted objects of a formset.
    :param form: Django form object to evaluate the fields that have been modified.
    :param formsets: List of Formsets.
    :return: String. Descriptions of the changes performed in the objects of the formset.
    """

    messages_list = [construct_change_message_for_form(form)]

    if formsets:
        for formset in formsets:
            if formset.model:
                for added_object in formset.new_objects:
                    messages_list.append(
                        _('Added %(name)s "%(object)s".').format(
                            name=force_text(added_object._meta.verbose_name),
                            object=force_text(added_object),
                        )
                    )

                for changed_object, changed_fields in formset.changed_objects:
                    messages_list.append(
                        _('Changed %(list)s for %(name)s "%(object)s".').format(
                            list=get_text_list(changed_fields, _('and')),
                            name=force_text(changed_object._meta.verbose_name),
                            object=force_text(changed_object)),
                    )

                for deleted_object in formset.deleted_objects:
                    messages_list.append(
                        _('Deleted {name} "{object}s".').format(
                            name=force_text(deleted_object._meta.verbose_name),
                            object=force_text(deleted_object)),
                    )

    change_message = ', '.join(messages_list)
    return change_message or _('No fields changed.')


def construct_change_message_extra_formsets(form, extra_formsets):

    messages_list = [construct_change_message_for_form(form)]

    for info in extra_formsets:
        if info['formset'].has_changed():
            messages_list.append('Updated {}'.format(info['title']))

    change_message = ' '.join(messages_list)
    return change_message or _('No fields changed.')


def get_concepts_for_apps(app_labels):
    from django.contrib.contenttypes.models import ContentType
    from aristotle_mdr import models as MDR
    models = ContentType.objects.filter(app_label__in=app_labels).all().order_by('model')
    concepts = [
        m
        for m in models
        if m.model_class() and issubclass(m.model_class(), MDR._concept) and
        not m.model.startswith("_")
    ]
    return concepts


error_messages = {
    "bulk_action_failed": "BULK_ACTION settings for registry are invalid.",
    "content_extensions_failed": "CONTENT_EXTENSIONS settings for registry are invalid.",
    "workgroup_changes_failed": "WORKGROUP_CHANGES settings for registry are invalid.",
    "dashboard_addons_failed": "DASHBOARD_ADDONS settings for registry are invalid.",
    "downloaders_failed": "DOWNLOADERS settings for registry are invalid.",
    "user_email_restrictions_failed": "USER_EMAIL_RESTRICTIONS settings for registry are invalid.",
}


def fetch_aristotle_settings() -> Dict:
    """
    Fetch Aristotle settings.
    :return: dict with all the aristotle settings.
    """
    if hasattr(settings, 'ARISTOTLE_SETTINGS_LOADER'):
        aristotle_settings = import_string(getattr(settings, 'ARISTOTLE_SETTINGS_LOADER'))()
    else:
        aristotle_settings = getattr(settings, 'ARISTOTLE_SETTINGS', {})

    strict_mode = getattr(settings, "ARISTOTLE_SETTINGS_STRICT_MODE", True) is not False
    aristotle_settings = validate_aristotle_settings(aristotle_settings, strict_mode)

    if settings.OVERRIDE_ARISTOTLE_SETTINGS:
        aristotle_settings.update(settings.OVERRIDE_ARISTOTLE_SETTINGS)
    return aristotle_settings


def validate_aristotle_settings(aristotle_settings, strict_mode):
    """
    This is a separate function to allow us to validate settings in areas apart from
    just fetching metadata.
    """

    # Check lists of string based items:
    for sub_setting, err in [
        ("BULK_ACTIONS", "bulk_action_failed"),
        ("WORKGROUP_CHANGES", "workgroup_changes_failed"),
        ("CONTENT_EXTENSIONS", "content_extensions_failed"),
        ("DASHBOARD_ADDONS", "dashboard_addons_failed"),
        ("DOWNLOADERS", "downloaders_failed"),
        # ("USER_EMAIL_RESTRICTIONS", "user_email_restrictions_failed")
    ]:
        try:
            check_settings=aristotle_settings.get(sub_setting, [])
            assert(type(check_settings) is list)
            assert(all(type(f) is str for f in check_settings))
        except Exception as e:
            logger.error(e)
            if strict_mode:
                raise ImproperlyConfigured(error_messages[err])
            else:
                aristotle_settings[sub_setting] = []

    return aristotle_settings


def fetch_metadata_apps():
    """
    Returns a list of all apps that provide metadata types
    """
    aristotle_apps = list(fetch_aristotle_settings().get('CONTENT_EXTENSIONS', []))
    aristotle_apps += ["aristotle_mdr"]
    aristotle_apps += ["aristotle_mdr_stewards"]
    aristotle_apps = list(set(aristotle_apps))

    return aristotle_apps


def is_active_module(module_name):
    aristotle_settings = fetch_aristotle_settings()
    in_apps = module_name in settings.INSTALLED_APPS

    if 'MODULES' in aristotle_settings:
        return in_apps and module_name in aristotle_settings['MODULES']
    else:
        return in_apps


def is_active_extension(extension_name):
    aristotle_settings = fetch_aristotle_settings()
    active = False

    if 'CONTENT_EXTENSIONS' in aristotle_settings:
        active = extension_name in aristotle_settings['CONTENT_EXTENSIONS']

    return active


def pandoc_installed() -> bool:
    installed = True
    try:
        _ensure_pandoc_path(quiet=True)
    except OSError:
        installed = False

    return installed


def fetch_aristotle_downloaders() -> List:
    downloaders: List = []
    unusable_imports: List = []
    enabled_downloaders: List = []

    imports = cache.get(settings.DOWNLOADERS_CACHE_KEY)
    if imports is None:
        installed = pandoc_installed()
        downloader_list = fetch_aristotle_settings().get('DOWNLOAD_OPTIONS', {}).get('DOWNLOADERS', [])
        if type(downloader_list) is dict:
            enabled_downloaders = [k for k, v in downloader_list.items() if v]
        elif type(downloader_list) is list:
            enabled_downloaders = downloader_list

        for imp in enabled_downloaders:
            downloader = import_string(imp)
            if (downloader.requires_pandoc and not installed):
                unusable_imports.append(imp)
            else:
                downloaders.append(downloader)
        for unusable in unusable_imports:
            enabled_downloaders.remove(unusable)
        cache.set(settings.DOWNLOADERS_CACHE_KEY, enabled_downloaders)
        return downloaders
    else:
        return [
            import_string(imp)
            for imp in imports
        ]


# Given a models label, id and name, Return a url to that objects page
# Used to avoid a database hit just to use get_absolute_url
def get_aristotle_url(label, obj_id, obj_name=None):

    label_list = label.split('.')

    app = label_list[0]
    cname = label_list[1]

    if obj_name:
        name_slug = slugify(obj_name)[:50]
    else:
        name_slug = None

    if app == 'aristotle_mdr':

        if cname in ['organization', 'workgroup', 'registrationauthority'] and name_slug is None:
            # Can't get these url's without name_slug
            return None

        concepts = [
            '_concept', 'objectclass', 'property', 'unitofmeasure', 'datatype',
            'conceptualdomain', 'valuedomain', 'dataelementconcept', 'dataelement', 'dataelementderivation'
        ]

        if cname in concepts:
            return reverse('aristotle:item', args=[obj_id])
        elif cname == 'organization':
            return reverse('aristotle:organization', args=[obj_id, name_slug])
        elif cname == 'workgroup':
            return reverse('aristotle:workgroup', args=[obj_id, name_slug])
        elif cname == 'registrationauthority':
            return reverse('aristotle:registrationAuthority', args=[obj_id, name_slug])

    elif app == 'aristotle_mdr_review_requests':
        if cname == 'reviewrequest':
            return reverse('aristotle_reviews:review_details', args=[obj_id])

    return None


def strip_tags(text: str) -> str:
    """This filter removes all the tags from a string."""
    return bleach.clean(text, tags=[], strip=True)


def get_concept_models() -> List[Model]:
    """Returns models for any concept subclass"""
    from aristotle_mdr.models import _concept
    models = []
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if issubclass(model, _concept) and model != _concept:
                models.append(model)
    return models


def get_names_of_concept_models() -> List[str]:
    """
    Returns a list of the names of the concept models.
    e.g. ['ClassificationScheme', 'Relation', ...]
    """
    return [model.__name__ for model in get_concept_models()]


def get_lowercase_names_of_concept_models() -> List[str]:
    """
    Returns a list of the lowercase names of the concept models.
    e.g. ['classificationscheme', 'relation', ...]
    """
    return [model.lower() for model in get_names_of_concept_models()]


def get_camelcase_names_of_concept_models() -> List[str]:
    """
    Returns a list of the lowercase names of the concept models.
    e.g. ['classificationScheme', 'relation', ...]
    """
    return [model[0].lower() + model[1:] for model in get_names_of_concept_models()]


def get_concept_content_types() -> Dict[Model, ContentType]:
    models = get_concept_models()
    return ContentType.objects.get_for_models(*models)


def get_concept_name_to_content_type() -> Dict[str, ContentType]:
    """Generate a mapping of the name of the concept (for use in URLs) to the ContentType"""
    return {concept.__name__.lower(): concept_type for concept, concept_type in get_concept_content_types().items()}


def get_content_type_to_concept_name() -> Dict[str, str]:
    return {str(content_type).replace(" ", ""): content_type.name.title()
            for content_type in get_concept_content_types().values()}


def get_managed_item_models() -> List[Model]:
    """Returns models for any managed item subclass"""
    from aristotle_mdr.utils.model_utils import ManagedItem
    models = []
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if issubclass(model, ManagedItem) and model != ManagedItem:
                models.append(model)
    return models


def get_concept_type_choices():
    return tuple([(model.pk, model.name.title()) for model in get_concept_content_types().values()])


def get_managed_content_types() -> Dict[Model, ContentType]:
    models = get_managed_item_models()
    return ContentType.objects.get_for_models(*models)


def pretify_camel_case(camelcase):
    return re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', camelcase)


def cascade_items_queryset(items=[]):
    from aristotle_mdr.models import _concept

    all_ids = []
    for item in items:

        # Can't cascade from _concept
        if isinstance(item, _concept):
            cascade = item.item.registry_cascade_items
        else:
            cascade = item.registry_cascade_items

        cascaded_ids = [a.id for a in cascade]

        cascaded_ids.append(item.id)
        all_ids.extend(cascaded_ids)

    return _concept.objects.filter(id__in=all_ids)


def get_cascaded_ids(items=[]):
    from aristotle_mdr.models import _concept

    all_cascaded_ids = []

    for item in items:
        if isinstance(item, _concept):
            # Can't cascade from concept
            cascade = item.item.registry_cascade_items
        else:
            cascade = item.registry_cascade_items

        cascaded_ids = [item.id for item in cascade]

        all_cascaded_ids.extend(cascaded_ids)

    return all_cascaded_ids


def get_status_change_details(queryset, ra, new_state):
    from aristotle_mdr.models import STATES, Status
    extra_info = {}
    subclassed_queryset = queryset.select_subclasses()
    statuses = Status.objects.filter(concept__in=queryset, registrationAuthority=ra).select_related('concept')
    statuses = statuses.valid().order_by("-registrationDate", "-created")

    # new_state_num = static_content['new_state']
    if new_state:
        new_state_text = str(STATES[new_state])
    else:
        new_state_text = 'Unchanged'

    # Build a dict mapping concepts to their status data
    # So that no additional status queries need to be made
    states_dict = {}
    for status in statuses:
        state_name = str(STATES[status.state])
        reg_date = status.registrationDate
        if status.concept.id not in states_dict:
            states_dict[status.concept.id] = {
                'name': state_name,
                'reg_date': reg_date,
                'state': status.state
            }

    any_have_higher_status = False
    for concept in subclassed_queryset:
        url = reverse('aristotle:registrationHistory', kwargs={'iid': concept.id})

        innerdict = {}
        # Get class name
        innerdict['type'] = concept.__class__.get_verbose_name()
        innerdict['concept'] = concept
        innerdict['has_higher_status'] = False

        try:
            state_info = states_dict[concept.id]
        except KeyError:
            state_info = ""

        if state_info:
            innerdict['old'] = {
                'url': url,
                'text': state_info['name'],
                'old_reg_date': state_info['reg_date']
            }
            innerdict['old_reg_date'] = state_info['reg_date']
            if new_state and state_info['state'] >= new_state:
                innerdict['has_higher_status'] = True
                any_have_higher_status = True

        innerdict['new_state'] = {'url': url, 'text': new_state_text}

        extra_info[concept.id] = innerdict

    return extra_info, any_have_higher_status


def get_model_label(model) -> str:
    return '.'.join([model._meta.app_label, model._meta.model_name])


def format_seconds(seconds: int) -> str:
    """Given a number of seconds format as X hours, X minutes, X seconds"""
    minutes, rseconds = divmod(seconds, 60)
    hours, rminutes = divmod(minutes, 60)
    strings = []
    if hours > 0:
        strings.append('{} hours'.format(hours))
    if rminutes > 0:
        strings.append('{} minutes'.format(rminutes))
    if rseconds > 0:
        strings.append('{} seconds'.format(rseconds))
    return ', '.join(strings)


def is_postgres() -> bool:
    """
    Checks whether the default database connection is to a postgres db
    Should be used before any postgres specific queries
    """
    from django.db import connection
    return connection.vendor == 'postgresql'


def cloud_enabled():
    from django.conf import settings
    return "aristotle_cloud" in settings.INSTALLED_APPS
