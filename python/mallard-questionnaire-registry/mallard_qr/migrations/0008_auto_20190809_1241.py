# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-08-09 02:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mallard_qr', '0007_auto_20190604_1201'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='collected_data_element',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='aristotle_mdr.DataElement'),
        ),
        migrations.AlterField(
            model_name='responsedomain',
            name='value_domain',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ValueDomain'),
        ),
    ]