# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-08-27 04:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0043_change_superseding'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='_concept',
            name='superseded_by',
        ),
    ]
