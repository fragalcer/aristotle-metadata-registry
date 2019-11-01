# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid


def gen_uuid(apps, schema_editor, model):
    MyModel = apps.get_model('aristotle_mdr', model)
    for row in MyModel.objects.all():
        row.uuid = uuid.uuid1()
        row.save()

def gen_concept_uuid(apps, schema_editor):
    gen_uuid(apps, schema_editor, '_concept')

def gen_measure_uuid(apps, schema_editor):
    gen_uuid(apps, schema_editor, 'measure')

def gen_organization_uuid(apps, schema_editor):
    gen_uuid(apps, schema_editor, 'organization')

def gen_workgroup_uuid(apps, schema_editor):
    gen_uuid(apps, schema_editor, 'workgroup')

class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0019_change_dataelementderives_to_m2m'),
    ]

    operations = [
        migrations.AddField(
            model_name='_concept',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, null=True),
        ),
        migrations.RunPython(gen_concept_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='_concept',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, unique=True, null=False,
                help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries'
            ),
        ),
        
        migrations.AddField(
            model_name='measure',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, null=True),
        ),
        migrations.RunPython(gen_measure_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='measure',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, unique=True, null=False,
                help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries'
            ),
        ),

        migrations.AddField(
            model_name='organization',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, null=True),
        ),
        migrations.RunPython(gen_organization_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='organization',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, unique=True, null=False,
                help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries'
            ),
        ),

        migrations.AddField(
            model_name='workgroup',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, null=True),
        ),
        migrations.RunPython(gen_workgroup_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='workgroup',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, unique=True, null=False,
                help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries'
            ),
        ),

    ]
