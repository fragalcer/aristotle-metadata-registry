"""
A Python "serializer". Doesn't do much serializing per se -- just converts to
and from basic Python data types (lists, dicts, strings, etc.). Useful as a basis for
other serializers.
"""
from __future__ import unicode_literals

from collections import OrderedDict

from django.conf import settings
from django.core.serializers import base
from django.core.exceptions import ObjectDoesNotExist
from django.db import DEFAULT_DB_ALIAS, models
from django.utils import six
from django.utils.encoding import force_text, is_protected_type
from django.core.serializers.python import Serializer as PySerializer
from aristotle_mdr import models as MDR

from aristotle_mdr.contrib.slots.models import Slot

import uuid
import datetime
import warnings
from reversion import revisions as reversion

import logging

logger = logging.getLogger(__name__)
logger.debug("Logging started for " + __name__)

excluded_fields = [
    "workgroup",
    "submitter",
]


def exclude_fields(obj, excludes):
    return [n.name for n in obj._meta.get_fields() if n.name not in excludes]


class Serializer(PySerializer):
    """
    Serializes a QuerySet to basic Python objects.
    """

    internal_use_only = True
    use_aristotle_ids = False

    def start_serialization(self):
        self._current = None
        self.objects = []

    def end_serialization(self):
        pass

    def start_object(self, obj):
        self._current = OrderedDict()

    def end_object(self, obj):
        self.objects.append(self.get_dump_object(obj))
        self._current = None

    def get_dump_object(self, obj):
        data = OrderedDict([('model', force_text(obj._meta))])
        if not self.use_natural_primary_keys or not hasattr(obj, 'natural_key'):
            data["pk"] = force_text(obj._get_pk_val(), strings_only=True)
        data['fields'] = self._current

        if 'aristotle_mdr.contrib.identifiers' in settings.INSTALLED_APPS:
            data['identifiers'] = [
                {
                    'namespace': {
                        'shorthand_prefix': scoped_id.namespace.shorthand_prefix,
                    },
                    'id': scoped_id.identifier,
                    'version': scoped_id.version
                }
                for scoped_id in obj.identifiers.all()
            ]

        if 'aristotle_mdr.contrib.slots' in settings.INSTALLED_APPS:

            try:
                user = self.options['context']['request'].user
            except KeyError:
                user = None

            if user:
                allowed_slots = Slot.objects.get_item_allowed(obj, user)
            else:
                allowed_slots = []

            data['slots'] = [
                {'name': slot.name, 'type': slot.type, 'value': slot.value}
                for slot in allowed_slots
            ]

        # if 'aristotle_mdr.contrib.links' in settings.INSTALLED_APPS:
        #     from aristotle_mdr.contrib.links import models as link_models
        #     obj_links = link_models.Link.objects.filter(linkend__concept=obj).all().distinct()
        #
        #     data['links'] = [
        #             [{
        #                 'relation': {
        #                     link.relation.uuid,
        #                 },
        #                 'members': [{
        #                     'concept': linkend.concept.uuid,
        #                     'role': linkend.role.name,
        #                     }]
        #                 }
        #             }
        #                 for linkend in link.linkend_set.all()
        #             ]
        #             for link in obj_links
        #         ]

        data['statuses'] = [
            {
                "change_details": status.changeDetails,
                "until_date": status.until_date,
                "registration_authority": status.registrationAuthority.uuid,
                "state": status.state,
                "state_meaning": status.get_state_display(),
                "registration_date": status.registrationDate
            }
            for status in obj.current_statuses()
        ]
        return data

    def handle_field(self, obj, field):
        value = field.value_from_object(obj)
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. All other values are
        # converted to string first.
        if is_protected_type(value):
            self._current[field.name] = value
        else:
            self._current[field.name] = field.value_to_string(obj)

    def handle_fk_field(self, obj, field):
        foreign_model = field.remote_field.model
        from aristotle_mdr.fields import ConceptForeignKey
        if type(field) is ConceptForeignKey:
            value = []

            if getattr(obj, field.get_attname()) is not None:
                value = foreign_model.objects.get(pk=getattr(obj, field.get_attname())).uuid
                # value = getattr(obj, field.get_attname()).uuid
            else:
                value = None

        elif self.use_natural_foreign_keys and hasattr(field.remote_field.model, 'natural_key'):
            related = getattr(obj, field.name)
            if related:
                value = related.natural_key()
            else:
                value = None
        else:
            value = getattr(obj, field.get_attname())
            if not is_protected_type(value):
                value = field.value_to_string(obj)
        self._current[field.name] = value

    def handle_m2m_field(self, obj, field):
        from aristotle_mdr.fields import ConceptManyToManyField
        foreign_model = field.remote_field
        if foreign_model.through._meta.auto_created:
            if type(field) is ConceptManyToManyField:
                def m2m_value(value):
                    return value.uuid
            elif self.use_natural_foreign_keys and hasattr(foreign_model.model, 'natural_key'):
                def m2m_value(value):
                    return value.natural_key()
            else:
                def m2m_value(value):
                    return force_text(value._get_pk_val(), strings_only=True)
            self._current[field.name] = [
                m2m_value(related) for related in getattr(obj, field.name).iterator()
            ]

    def getvalue(self):
        return self.objects

    def serialize(self, queryset, **options):
        """
        Serialize a queryset.
        """
        self.options = options

        self.stream = options.pop("stream", six.StringIO())
        self.selected_fields = options.pop("fields", None)
        self.use_natural_keys = options.pop("use_natural_keys", False)
        if self.use_natural_keys:
            from django.utils.deprecation import RemovedInDjango30Warning
            warnings.warn("``use_natural_keys`` is deprecated; use ``use_natural_foreign_keys`` instead.",
                          RemovedInDjango30Warning)
        self.use_natural_foreign_keys = options.pop('use_natural_foreign_keys', False) or self.use_natural_keys
        self.use_natural_primary_keys = options.pop('use_natural_primary_keys', False)

        self.start_serialization()
        self.first = True
        for obj in queryset:
            self.start_object(obj)
            # Use the concrete parent class' _meta instead of the object's _meta
            # This is to avoid local_fields problems for proxy models. Refs #17717.
            concrete_model = obj  # ._meta.concrete_model
            for field in obj._meta.fields:  # concrete_model._meta.local_fields:
                if field.name.startswith('_') or field.name in excluded_fields:
                    # Skip cached / protected fields
                    continue

                if field.serialize:
                    if field.remote_field is None:
                        if self.selected_fields is None or field.attname in self.selected_fields:
                            self.handle_field(obj, field)
                    else:
                        if self.selected_fields is None or field.attname[:-3] in self.selected_fields:
                            self.handle_fk_field(obj, field)
            for field in concrete_model._meta.many_to_many:
                if field.serialize:
                    if self.selected_fields is None or field.attname in self.selected_fields:
                        self.handle_m2m_field(obj, field)

            if hasattr(obj, 'serialize_weak_entities'):  # and field.name in dict(obj.serialize_weak_entities).keys():

                for f, field in getattr(obj, 'serialize_weak_entities'):
                    weak_field = field
                    foreign_model = getattr(obj.__class__, weak_field).rel.related_model
                    parent_field = getattr(obj.__class__, weak_field).rel.remote_field.name
                    weak_serial = []
                    for related in getattr(obj, weak_field).all():
                        ser = {}
                        for subfield in related._meta.fields:
                            if subfield.name in exclude_fields(foreign_model, ['id', parent_field]):
                                v = getattr(related, subfield.name)
                                if issubclass(type(v), MDR._concept):
                                    ser[subfield.name] = getattr(related, subfield.name).uuid
                                else:
                                    ser[subfield.name] = getattr(related, subfield.name)
                        weak_serial.append(ser)
                    self._current[f] = weak_serial
            superseded_by = obj.superseded_by_items.first()
            if superseded_by:
                superseded_by = superseded_by.uuid
            else:
                superseded_by = None
            self._current["superseded_by"] = superseded_by

            self.end_object(obj)
            if self.first:
                self.first = False
        self.end_serialization()
        return self.getvalue()


# @transaction.atomic()
def Deserializer(manifest, **options):
    """
    Deserialize simple Python objects back into Django ORM instances.

    It's expected that you pass the Python objects themselves (instead of a
    stream or a string) to the constructor
    """
    db = options.pop('using', DEFAULT_DB_ALIAS)
    ignore = options.pop('ignorenonexistent', False)
    field_names_cache = {}  # Model: <list of field_names>

    from aristotle_mdr.models import RegistrationAuthority
    for ra in manifest.get('registration_authorities', []):
        if ra['uuid']:
            ra = RegistrationAuthority.objects.update_or_create(
                uuid=ra['uuid'],
                defaults={
                    'name': ra['name'],
                    'definition': ra['definition'],
                }
            )
        else:
            ra = RegistrationAuthority.objects.create(
                # uuid=ra['uuid'],
                name=ra['name'],
                definition=ra['definition']
            )

    from aristotle_mdr.models import Organization
    for org in manifest.get('organizations', []):
        o, _ = Organization.objects.get_or_create(
            name=org['name'],
            definition=org['definition'],
            uuid=org['uuid'],
        )

        if 'aristotle_mdr.contrib.identifiers' in settings.INSTALLED_APPS:
            from aristotle_mdr.contrib.identifiers.models import Namespace
            for namespace in org['namespaces']:
                Namespace.objects.get_or_create(
                    naming_authority=o,
                    shorthand_prefix=namespace['shorthand_prefix']
                )

    for d in manifest['metadata']:
        # Look up the model and starting build a dict of data for it.
        try:
            from django.contrib.contenttypes.models import ContentType

            Model = ContentType.objects.get(
                app_label=d["concept_type"]["app"], model=d["concept_type"]["model"]
            ).model_class()

        except base.DeserializationError:
            if ignore:
                continue
            else:
                raise
        data = {}
        if 'pk' in d:
            try:
                data[Model._meta.pk.attname] = Model._meta.pk.to_python(d.get('pk'))
            except Exception as e:
                raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), None)
        m2m_data = {}

        if Model not in field_names_cache:
            field_names_cache[Model] = {f.name for f in Model._meta.get_fields()}
        field_names = field_names_cache[Model]

        # Handle each field
        for (field_name, field_value) in six.iteritems(d["fields"]):

            if ignore and field_name not in field_names:
                # skip fields no longer on model
                continue

            if isinstance(field_value, str):
                field_value = force_text(
                    field_value, options.get("encoding", settings.DEFAULT_CHARSET), strings_only=True
                )

            if field_name in dict(getattr(Model, 'serialize_weak_entities', {})).keys():
                pass  # Wait
            else:
                field = Model._meta.get_field(field_name)

                # Handle M2M relations
                if field.remote_field and isinstance(field.remote_field, models.ManyToManyRel):
                    model = field.remote_field.model
                    if hasattr(model._default_manager, 'get_by_natural_key'):
                        def m2m_convert(value):
                            if hasattr(value, '__iter__') and not isinstance(value, six.text_type):
                                return model._default_manager.db_manager(db).get_by_natural_key(*value).pk
                            else:
                                return force_text(model._meta.pk.to_python(value), strings_only=True)
                    else:
                        def m2m_convert(value):
                            return force_text(model._meta.pk.to_python(value), strings_only=True)

                    try:
                        m2m_data[field.name] = []
                        for pk in field_value:
                            m2m_data[field.name].append(m2m_convert(pk))
                    except Exception as e:
                        raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), pk)

                # Handle FK fields
                elif field.remote_field and isinstance(field.remote_field, models.ManyToOneRel):
                    model = field.remote_field.model
                    if field_value is not None:
                        try:
                            default_manager = model._default_manager
                            field_name = field.remote_field.field_name
                            if issubclass(model, MDR._concept):
                                value, c = model.objects.get_or_create(uuid=field_value, defaults={
                                    'name': "no name",
                                    'definition': 'no definition'
                                })
                                data[field.attname] = value.pk
                                # _meta.get_field(field_name).to_python(field_value)
                            elif hasattr(model, 'uuid'):
                                try:
                                    value = model.objects.get(uuid=field_value)
                                except ObjectDoesNotExist:
                                    # Need to raise error here
                                    pass
                                data[field.attname] = value.pk
                            elif hasattr(default_manager, 'get_by_natural_key'):
                                if hasattr(field_value, '__iter__') and not isinstance(field_value, six.text_type):
                                    obj = default_manager.db_manager(db).get_by_natural_key(*field_value)
                                    value = getattr(obj, field.remote_field.field_name)
                                    # If this is a natural foreign key to an object that
                                    # has a FK/O2O as the foreign key, use the FK value
                                    if model._meta.pk.remote_field:
                                        value = value.pk
                                else:
                                    value = model._meta.get_field(field_name).to_python(field_value)
                                data[field.attname] = value
                            else:
                                data[field.attname] = model._meta.get_field(field_name).to_python(field_value)
                        except Exception as e:
                            raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)
                    else:
                        data[field.attname] = None

                # Handle all other fields
                else:
                    try:
                        data[field.name] = field.to_python(field_value)
                    except Exception as e:
                        raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)

        with reversion.create_revision():
            obj = build_instance(Model, data, db)
            obj.save()  # Get it in the database.

            for (field_name, field_value) in six.iteritems(d["fields"]):
                weak_entities = dict(getattr(Model, 'serialize_weak_entities', {}))
                if field_name in weak_entities.keys():
                    rel = getattr(
                        Model,
                        weak_entities.get(field_name)
                    )
                    RelModel = rel.rel.related_model
                    other_side = rel.rel.remote_field.name
                    for weak_entity in field_value:
                        # Boy this would be easier if uuids were primary keys :/
                        # Check if any fields are concepts
                        for sub_field_name, sub_value in weak_entity.items():
                            sub_field = RelModel._meta.get_field(sub_field_name)
                            if sub_field.remote_field and isinstance(sub_field.remote_field, models.ManyToOneRel):
                                sub_model = sub_field.remote_field.model
                                if issubclass(sub_model, MDR._concept):
                                    # We have to hope this becomes consistent
                                    sub_obj, c = sub_model.objects.get_or_create(uuid=sub_value, defaults={
                                        'name': "no name",
                                        'definition': 'no definition'
                                    })
                                    weak_entity[sub_field_name] = sub_obj

                        weak_entity.update({other_side: obj})
                        RelModel.objects.update_or_create(**weak_entity)

            if 'aristotle_mdr.contrib.slots' in settings.INSTALLED_APPS:
                from aristotle_mdr.contrib.slots.models import Slot
                for slot in d.get("slots", []):
                    Slot.objects.get_or_create(**{
                        'concept': obj,
                        'name': slot['name'],
                        'type': slot.get('type', ''),
                        'value': slot['value'],
                    })
            if 'aristotle_mdr.contrib.identifiers' in settings.INSTALLED_APPS:
                from aristotle_mdr.contrib.identifiers.models import ScopedIdentifier, Namespace
                for identifier in d.get("identifiers", []):
                    try:
                        org = Organization.objects.get(uuid=identifier['namespace']['naming_authority'])
                        namespace, c = Namespace.objects.get_or_create(
                            shorthand_prefix=identifier['namespace']['shorthand_prefix'],
                            naming_authority=org
                        )
                        ScopedIdentifier.objects.get_or_create(**{
                            'concept': obj,
                            'identifier': identifier['identifier'],
                            'version': identifier.get('version', ""),
                            'namespace': namespace
                        })
                    except Exception as e:
                        logger.warning(e)
                        raise
                        # TODO: Better error logging

            for status in d.get("statuses", []):
                ra, created = MDR.RegistrationAuthority.objects.get_or_create(
                    uuid=uuid.UUID(status["registration_authority"]),
                    defaults={'name': 'Unknown Registration Authority'}
                )
                if created:
                    pass  # TODO: Log something useful
                state = {
                    "changeDetails": status.get("change_details", ""),
                    "until_date": status.get("until_date", None),
                    "registrationAuthority": ra,
                    "state": int(status["state"]),
                    "registrationDate": datetime.datetime.strptime(status["registration_date"], '%Y-%m-%d'),
                    "concept": obj
                }
                st, c = MDR.Status.objects.get_or_create(**state)

            if "links" in d.keys() and 'aristotle_mdr.contrib.links' in settings.INSTALLED_APPS:
                from aristotle_mdr.contrib.links import models as link_models
                # obj_links = link_models.Link.objects.filter(linkend__concept=obj).all().distinct()

                link_models.Link.objects.filter(linkend__concept=obj).all().distinct().delete()
                for data in d.get("links", []):
                    rel = link_models.Relation.objects.get(uuid=data['relation'])
                    link = link_models.Link.objects.create(relation=rel)
                    for ordinal, m in enumerate(data['members']):
                        concept = MDR._concept.objects.get(uuid=m['concept'])
                        role, c = link_models.RelationRole.objects.get_or_create(
                            name=m['link'],
                            defaults={
                                "relation": rel,
                                "ordinal": 0,
                            }
                        )
                        link_models.LinkEnd.objects.update_or_create(
                            link=link,
                            role=role,
                            concept=concept
                        )

            yield base.DeserializedObject(obj, m2m_data)


def build_instance(model, data, db):
    """
    Build a model instance.
    If the model instance doesn't have a primary key and the model supports
    natural keys, try to retrieve it from the database.
    """
    obj = model(**data)
    if obj.pk is None and hasattr(model, 'uuid'):
        try:
            obj.pk = model._default_manager.db_manager(db).get(uuid=obj.uuid).pk
        except model.DoesNotExist:
            pass
    return obj
