# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-02-26 05:36
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0052_auto_20190218_0417'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dataelementderivation',
            name='derives',
        ),
        migrations.RemoveField(
            model_name='dataelementderivation',
            name='inputs',
        ),
    ]
