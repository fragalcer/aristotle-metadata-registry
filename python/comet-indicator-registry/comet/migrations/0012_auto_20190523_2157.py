# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-23 11:57
from __future__ import unicode_literals

import ckeditor_uploader.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0011_auto_20190427_2149'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='indicator',
            name='denominator_computation',
        ),
        migrations.RemoveField(
            model_name='indicator',
            name='numerator_computation',
        ),
        migrations.AddField(
            model_name='qualitystatement',
            name='institutional_environment',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
    ]
