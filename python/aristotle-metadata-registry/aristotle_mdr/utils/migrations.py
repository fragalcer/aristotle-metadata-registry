"""
This file contains code required for the v1.3.x -> 1.4.x data migrations
At some point, we will squash the entire migration path for <1.4 and remove this before we have too many users
running this code.
"""
from django.db import migrations
from django.db.migrations.operations.base import Operation


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
