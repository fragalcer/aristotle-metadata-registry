# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0015_concept_field_fixer_part3'),
    ]

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('questionText', models.TextField(null=True, blank=True)),
                ('responseLength', models.PositiveIntegerField(null=True, blank=True)),
                ('collectedDataElement', models.ForeignKey(related_name='questions', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='Questionnaire',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('questions', models.ManyToManyField(related_name='questionnaires', null=True, to='extension_test.Question', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='TargetRespondentClass',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rationale', models.TextField(null=True, blank=True)),
                ('questionnaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='extension_test.Questionnaire')),
                ('respondent_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ObjectClass')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='questionnaire',
            name='respondent_classes',
            field=models.ManyToManyField(to='aristotle_mdr.ObjectClass', through='extension_test.TargetRespondentClass'),
        ),
    ]
