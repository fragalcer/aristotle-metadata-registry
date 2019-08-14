# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0011_update_ckeditor_remove_d19_errors'),
    ]

    operations = [
        migrations.CreateModel(
            name='Slot',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('value', models.CharField(max_length=256)),
                ('concept', models.ForeignKey(related_name='slots', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SlotDefinition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('app_label', models.CharField(help_text='Add an app for app specific help, required for concept help', max_length=256)),
                ('concept_type', models.CharField(max_length=256)),
                ('slot_name', models.CharField(max_length=256)),
                ('help_text', models.TextField(max_length=256, null=True, blank=True)),
                ('cardinality', models.IntegerField(default=0, help_text='Specifies if the slot can be stored multiple times.', choices=[(0, 'Singleton (0..1)'), (1, 'Repeatable (0..n)')])),
                ('datatype', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataType', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='slot',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_slots.SlotDefinition'),
        ),
    ]
