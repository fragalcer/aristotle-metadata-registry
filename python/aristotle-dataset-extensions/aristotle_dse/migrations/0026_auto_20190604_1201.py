# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-06-04 02:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0025_auto_20190528_1918'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dataset',
            old_name='accrual_periodicity',
            new_name='frequency',
        ),
        migrations.RemoveField(
            model_name='datacatalog',
            name='publisher',
        ),
        migrations.RemoveField(
            model_name='dataset',
            name='publisher',
        ),
        migrations.RemoveField(
            model_name='distribution',
            name='publisher',
        ),
        migrations.AlterField(
            model_name='dataset',
            name='dct_modified',
            field=models.DateTimeField(blank=True, help_text='Most recent date on which the dataset was changed, updated or modified.', null=True, verbose_name='Modification date'),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='dct_modified',
            field=models.DateTimeField(blank=True, help_text='Most recent date on which the catalog was changed, updated or modified.', null=True, verbose_name='Modification date'),
        ),


        migrations.RenameField(
            model_name='dssclusterinclusion',
            old_name='maximum_occurances',
            new_name='maximum_occurrences',
        ),
        migrations.RenameField(
            model_name='dssdeinclusion',
            old_name='maximum_occurances',
            new_name='maximum_occurrences',
        ),
        migrations.AlterField(
            model_name='dssclusterinclusion',
            name='maximum_occurrences',
            field=models.PositiveIntegerField(default=1, help_text='The maximum number of times a item can be included in a dataset', verbose_name='Maximum Occurrences'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='dssdeinclusion',
            name='maximum_occurrences',
            field=models.PositiveIntegerField(default=1, help_text='The maximum number of times a item can be included in a dataset', verbose_name='Maximum Occurrences'),
            preserve_default=False,
        ),
    ]
