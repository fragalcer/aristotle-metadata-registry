# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-07-11 06:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0012_auto_20190523_2157'),
    ]

    operations = [
        migrations.AlterField(
            model_name='frameworkdimension',
            name='level',
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name='frameworkdimension',
            name='lft',
            field=models.PositiveIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name='frameworkdimension',
            name='rght',
            field=models.PositiveIntegerField(editable=False),
        ),
    ]