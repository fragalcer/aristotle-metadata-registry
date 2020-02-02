# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations, models
import uuid


def gen_indicatorset_uuid(apps, schema_editor):
    MyModel = apps.get_model('comet', 'indicatorsettype')
    for row in MyModel.objects.all():
        row.uuid = uuid.uuid1()
        row.save()


class Migration(migrations.Migration):

    replaces = [('comet', '0002_indicatorsettype_uuid'), ('comet', '0003_auto_20170714_1609')]

    dependencies = [
        ('comet', '0001_squashed_0008_fix_concept_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicatorsettype',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, null=True),
        ),
        migrations.RunPython(gen_indicatorset_uuid, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='indicatorsettype',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, unique=True, null=False,
                                   help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries'
                                   ),
        ),
        migrations.AlterField(
            model_name='indicator',
            name='denominators',
            field=models.ManyToManyField(related_name='as_denominator', to='aristotle_mdr.DataElement', blank=True),
        ),
    ]
