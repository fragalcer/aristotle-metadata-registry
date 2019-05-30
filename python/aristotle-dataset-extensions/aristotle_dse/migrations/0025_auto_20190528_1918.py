# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-29 00:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0024_auto_20190501_2242'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dssclusterinclusion',
            name='reference',
            field=models.CharField(blank=True, default='', help_text='Optional field for refering to this item within the DSS.', max_length=512),
        ),
        migrations.AlterField(
            model_name='dssdeinclusion',
            name='reference',
            field=models.CharField(blank=True, default='', help_text='Optional field for refering to this item within the DSS.', max_length=512),
        ),
    ]
