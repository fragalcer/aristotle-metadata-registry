"""
This file contains code required for the v1.3.x -> 1.4.x data migrations
At some point, we will squash the entire migration path for <1.4 and remove this before we have too many users
running this code.
"""
import django.db.models
from django.db import migrations, models
from django.db.migrations.operations.base import Operation
from django.conf import settings

import ckeditor_uploader.fields
from .utils import classproperty


def move_field_to_slot(apps, schema_editor, field_name):

    try:
        slot = apps.get_model('aristotle_mdr_slots', 'Slot')
    except LookupError:
        slot = None

    if slot:
        _concept = apps.get_model('aristotle_mdr', '_concept')

        for concept in _concept.objects.all():
            if getattr(concept, field_name):
                slot.objects.create(
                    name=field_name,
                    concept=concept,
                    value=getattr(concept, field_name)
                )
    else:
        print("Data migration could not be completed")


def move_slot_to_field(apps, schema_editor, field_name, maxlen=200):

    try:
        slot = apps.get_model('aristotle_mdr_slots', 'Slot')
    except LookupError:
        slot = None

    if slot:
        _concept = apps.get_model('aristotle_mdr', '_concept')

        for s in slot.objects.all():
            if s.name == field_name and len(s.value) < maxlen:

                try:
                    concept = _concept.objects.get(pk=s.concept.pk)
                except concept.DoesNotExist:
                    concept = None
                    print('Could not find concept with id {} Found through slot {}'.format(s.concept.pk, s))

                if concept:
                    setattr(concept, field_name, s.value)
                    concept.save()
    else:
        print('Reverse data migration could not be completed')


class StewardMigration(migrations.Migration):
    so_uuid = None
    steward_pattern = "Default Steward for {name}"

    @classmethod
    def add_stewardship_org(cls, apps, schema_editor):
        StewardOrganisation = apps.get_model('aristotle_mdr', 'StewardOrganisation')
        StewardMembership = apps.get_model('aristotle_mdr', 'StewardOrganisationMembership')
        from django.conf import settings
        name = cls.steward_pattern.format(name=settings.ARISTOTLE_SETTINGS['SITE_NAME'])
        so, _ = StewardOrganisation.objects.get_or_create(name=name)
        from django.contrib.auth import get_user_model
        User = apps.get_model('aristotle_mdr_user_management', 'User')

        if settings.MIGRATION_PRINT:
            print("\n=================")
            print("Autocreating default Stewardship Organization .... \"%s\"" % (so.name, ))
            print("All registration authorities and workgroups will be assigned to this Organization")
            print("All metadata assigned to a workgroups or registered will also be assigned to this Organization")
            print("Update this name once all migrations are complete.")
            print("-----------------")

        for u in User.objects.all().order_by("-is_superuser"):
            # We can't access methods during migrations so we manually create memberships
            # Also migrations don't work well with the proxy "AUTH_USER", so we just add in the primary key
            if u.is_superuser:
                role = "admin"
            else:
                role = "member"
            print("Granting [{user}] the role [{role}]".format(user=u.email, role=role))
            StewardMembership.objects.get_or_create(group=so, user=u, role=role)

        if settings.MIGRATION_PRINT:
            print("=================")
        return so.uuid

    @classmethod
    def get_uuid(cls):
        return cls.so_uuid

    @classmethod
    def fetch_stewardship_org_uuid(cls, apps, schema_editor):
        StewardOrganisation = apps.get_model('aristotle_mdr', 'StewardOrganisation')
        from django.conf import settings
        name = cls.steward_pattern.format(name=settings.ARISTOTLE_SETTINGS['SITE_NAME'])
        so = StewardOrganisation.objects.order_by("id").first()  # get(name=name)
        cls.stewardorganisation = so
        cls.so_uuid = so.uuid
        return so.uuid

    @classmethod
    def assign_orgs_to_metadata(cls, apps, schema_editor):
        _concept = apps.get_model('aristotle_mdr', '_concept')
        for item in _concept.objects.all():
            if item.workgroup is not None:
                item.stewardship_organisation = item.workgroup.stewardship_organisation
                item.save()

    @classmethod
    def assign_orgs_to_model(cls, apps, schema_editor, model_name):
        model = apps.get_model('aristotle_mdr', model_name)
        for item in model.objects.all():
            item.stewardship_organisation_id = cls.so_uuid
            item.save()


def create_uuid_objects(app_label, model_name, migrate_self=True):
    def inner(apps, schema_editor):
        from aristotle_mdr.models import UUID, baseAristotleObject
        from django.apps import apps as apppps
        from django.contrib.contenttypes.models import ContentType

        object_type = apppps.get_model(app_label, model_name)
        if not issubclass(object_type, baseAristotleObject):
            return

        for ct in ContentType.objects.all():
            kls = ct.model_class()
            if kls is None:
                # Uninstalled app
                continue
            if not issubclass(kls, baseAristotleObject):
                continue
            if not issubclass(kls, object_type):
                continue
            if kls is object_type and not migrate_self:
                continue

            for instance in kls.objects.all():
                details = dict(
                    app_label=instance._meta.app_label,
                    model_name=instance._meta.model_name,
                )

                u, c = UUID.objects.get_or_create(
                    uuid=instance.uuid_id,
                    defaults=details
                )
                if issubclass(kls, object_type) and kls is not object_type:
                    u.app_label=instance._meta.app_label
                    u.model_name=instance._meta.model_name
                    u.save()

    return inner


class DBOnlySQL(migrations.RunSQL):

    reversible = True

    def __init__(self, *args, **kwargs):
        self.vendor = kwargs.pop('vendor')
        super().__init__(*args, **kwargs)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == self.vendor:
            return super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == self.vendor:
            return super().database_backwards(app_label, schema_editor, from_state, to_state)


class MoveConceptFields(Operation):

    reversible = False

    def __init__(self, model_name):
        self.model_name = model_name

    def state_forwards(self, app_label, state):
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):

        if schema_editor.connection.vendor == 'sqlite':
            concept_table_name = "%s_%s" % (app_label, self.model_name)
            for column in [
                'comments', 'origin_URI', 'references', 'responsible_organisation',
                'short_name', 'submitting_organisation', 'superseded_by_id',
                'synonyms', 'version'
            ]:
                base_query = """
                    update aristotle_mdr__concept
                        set temp_col_%s = (
                            select "%s"."%s"
                            from %s
                            where %s._concept_ptr_id = aristotle_mdr__concept.id
                        )
                        where exists ( select * from %s where %s._concept_ptr_id = aristotle_mdr__concept.id)
                """ % tuple(
                    [column, concept_table_name, column, concept_table_name, concept_table_name, concept_table_name, concept_table_name]
                )
                schema_editor.execute(base_query)
        else:
            concept_table_name = "%s_%s" % (app_label, self.model_name)
            base_query = """
                UPDATE  "aristotle_mdr__concept"
                SET     "temp_col_comments" = "%s"."comments",
                        "temp_col_origin_URI" = "%s"."origin_URI",
                        "temp_col_references" = "%s"."references",
                        "temp_col_responsible_organisation" = "%s"."responsible_organisation",
                        "temp_col_short_name" = "%s"."short_name",
                        "temp_col_submitting_organisation" = "%s"."submitting_organisation",
                        "temp_col_superseded_by_id" = "%s"."superseded_by_id",
                        "temp_col_synonyms" = "%s"."synonyms",
                        "temp_col_version" = "%s"."version"
                FROM    %s
                WHERE   "aristotle_mdr__concept"."id" = "%s"."_concept_ptr_id"
                ;
            """ % tuple([concept_table_name] * 11)
            schema_editor.execute(base_query)

    def describe(self):
        return "Creates extension %s" % self.name


class ConceptMigrationAddConceptFields(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='_concept',
            name='temp_col_comments',
            field=ckeditor_uploader.fields.RichTextUploadingField(help_text='Descriptive comments about the metadata item.', blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_origin_URI',
            field=models.URLField(help_text='If imported, the original location of the item', blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_references',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_responsible_organisation',
            field=models.CharField(max_length=256, blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_short_name',
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_submitting_organisation',
            field=models.CharField(max_length=256, blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_superseded_by',
            field=models.ForeignKey(related_name='supersedes', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', null=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_synonyms',
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='temp_col_version',
            field=models.CharField(max_length=20, blank=True),
        ),
    ]


class ConceptMigration(migrations.Migration):

    @classproperty
    def operations(cls):
        copy_operations = []
        delete_operations = []

        for model in cls.models_to_fix:
            copy_operations.append(MoveConceptFields(model_name=model))
            delete_operations += [
                migrations.RemoveField(
                    model_name=model,
                    name='comments',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='origin_URI',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='references',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='responsible_organisation',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='short_name',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='submitting_organisation',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='superseded_by',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='synonyms',
                ),
                migrations.RemoveField(
                    model_name=model,
                    name='version',
                )
            ]
        return copy_operations + delete_operations


class ConceptMigrationRenameConceptFields(migrations.Migration):
    operations = [
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_comments',
            new_name='comments',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_origin_URI',
            new_name='origin_URI',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_references',
            new_name='references',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_responsible_organisation',
            new_name='responsible_organisation',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_short_name',
            new_name='short_name',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_submitting_organisation',
            new_name='submitting_organisation',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_superseded_by',
            new_name='superseded_by',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_synonyms',
            new_name='synonyms',
        ),
        migrations.RenameField(
            model_name='_concept',
            old_name='temp_col_version',
            new_name='version',
        ),
    ]


# def copy_field(apps, schema_editor, field_name):
#     """
#     Copy the value of a field from an organisation to the RA.
#     """
#     RAClass = apps.get_model('aristotle_mdr', 'RegistrationAuthority')
#     OrgClass = apps.get_model('aristotle_mdr', 'Organization')

#     # Thanks: https://stackoverflow.com/questions/12518560/django-update-table-using-data-from-another-table
#     from django.db.models import Subquery, OuterRef

#     org_val = OrgClass.objects.filter(
#         id=OuterRef('organization_ptr')
#     ).values_list(
#         field_name
#     )[:1]

#     RAClass.objects.all().update(**{
#         # "new_"+field_name: F(field_name)
#         ""+field_name: Subquery(org_val)
#     })


# https://code.djangoproject.com/ticket/23521
class AlterBaseOperation(Operation):
    reduce_to_sql = False
    reversible = True

    def __init__(self, model_name, bases, prev_bases):
        self.model_name = model_name
        self.bases = bases
        self.prev_bases = prev_bases

    def state_forwards(self, app_label, state):
        state.models[app_label, self.model_name].bases = self.bases
        state.reload_model(app_label, self.model_name)

    def state_backwards(self, app_label, state):
        state.models[app_label, self.model_name].bases = self.prev_bases
        state.reload_model(app_label, self.model_name)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def describe(self):
        return "Update %s bases to %s" % (self.model_name, self.bases)


class CustomFieldMover(Operation):
    reduce_to_sql = False
    reversible = True
    atomic = None

    def __init__(
        self, app_label, model_name, field_name,
        custom_field_name=None, custom_field_type="str",
        custom_field_kwargs={}
    ):
        self.app_label = app_label
        self.model_name = model_name
        self.field_name = field_name
        self.custom_field_name = custom_field_name or field_name
        self.custom_field_type = custom_field_type
        self.custom_field_kwargs = custom_field_kwargs

    def describe(self):
        return "Move field to custom field for " % (self.model_name, self.bases)

    def state_forwards(self, app_label, state):
        pass

    def state_backwards(self, app_label, state):
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        apps = from_state.apps

        ContentType = apps.get_model('contenttypes', 'ContentType')
        if ContentType.objects.count() == 0:
            # Below forces content types to be created for the migrated items
            # In production, contenttypes should already be loaded
            from django.contrib.contenttypes.management import create_contenttypes
            app_config = apps.get_app_config(self.app_label.lower())
            app_config.models_module = app_config.models_module or True
            create_contenttypes(app_config)

        # Only add custom field if there are any items
        MigratedModel = apps.get_model(self.app_label, self.model_name)
        if MigratedModel.objects.count() == 0:
            return

        CustomField = apps.get_model('aristotle_mdr_custom_fields', 'CustomField')
        CustomValue = apps.get_model('aristotle_mdr_custom_fields', 'CustomValue')

        ctype = ContentType.objects.get(
            app_label=self.app_label.lower(),
            model=self.model_name.lower(),
        )

        custom_field, c = CustomField.objects.get_or_create(
            name=self.custom_field_name,
            type=self.custom_field_type,
            allowed_model=ctype,
            defaults=self.custom_field_kwargs
        )

        for obj in MigratedModel.objects.all():
            if getattr(obj, self.field_name):
                CustomValue.objects.create(
                    field=custom_field,
                    concept=obj,
                    content=getattr(obj, self.field_name)
                )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass
