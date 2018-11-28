# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-11-28 05:09
from __future__ import unicode_literals

import aristotle_mdr.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aristotle_mdr', '0046_auto_20181107_0433'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomField',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('name', models.CharField(max_length=1000)),
                ('type', models.CharField(choices=[('int', 'Integer'), ('str', 'String'), ('html', 'Rich Text'), ('date', 'Date')], max_length=10)),
                ('help_text', models.CharField(max_length=1000)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CustomValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('content', models.TextField()),
                ('concept', aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_custom_fields.CustomField')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
