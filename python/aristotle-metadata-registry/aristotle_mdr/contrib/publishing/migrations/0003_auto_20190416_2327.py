# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-17 04:27
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_publishing', '0002_versionpermissions'),
    ]

    operations = [
        migrations.RenameField(
            model_name='versionpermissions',
            old_name='visibility_permission',
            new_name='visibility',
        ),
    ]
