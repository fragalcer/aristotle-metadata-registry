# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-13 03:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_custom_fields', '0003_auto_20190408_1059'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfield',
            name='state',
            field=models.IntegerField(choices=[(0, 'Active & Visible'), (1, 'Inactive & Visible'), (2, 'Inactive & Hidden')], default=0),
        ),
    ]
