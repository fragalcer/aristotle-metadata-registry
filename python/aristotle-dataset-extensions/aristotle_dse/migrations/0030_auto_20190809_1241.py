# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-08-09 02:41
from __future__ import unicode_literals

import aristotle_mdr.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0029_auto_20190711_0117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='catalog',
            field=models.ForeignKey(blank=True, help_text='An entity responsible for making the dataset available.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_dse.DataCatalog'),
        ),
        migrations.AlterField(
            model_name='datasetspecification',
            name='statistical_unit',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='A Statistical Unit is the Object Class that is recorded against each entry described by this specification', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='statistical_unit_of', to='aristotle_mdr._concept', verbose_name='Statistical Unit'),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='dataset',
            field=models.ForeignKey(blank=True, help_text='Connects a distribution to its available datasets', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_dse.Dataset'),
        ),
        migrations.AlterField(
            model_name='distributiondataelementpath',
            name='data_element',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='An entity responsible for making the dataset available.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.DataElement', verbose_name='Data Element'),
        ),
        migrations.AlterField(
            model_name='dssdeinclusion',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_dse.DSSGrouping'),
        ),
    ]
