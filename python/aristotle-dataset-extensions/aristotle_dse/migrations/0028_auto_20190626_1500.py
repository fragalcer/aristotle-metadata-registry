# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-06-26 05:00
from __future__ import unicode_literals

import ckeditor_uploader.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0027_auto_20190624_1215'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dssclusterinclusion',
            old_name='cardinality',
            new_name='inclusion',
        ),
        migrations.RenameField(
            model_name='dssclusterinclusion',
            old_name='conditional_obligation',
            new_name='conditional_inclusion',
        ),
        migrations.RenameField(
            model_name='dssdeinclusion',
            old_name='cardinality',
            new_name='inclusion',
        ),
        migrations.RenameField(
            model_name='dssdeinclusion',
            old_name='conditional_obligation',
            new_name='conditional_inclusion',
        ),
    ]
