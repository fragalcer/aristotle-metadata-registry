# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-01-18 03:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_backwards', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classificationscheme',
            name='classificationStructure',
            field=models.TextField(blank=True),
        ),
    ]
