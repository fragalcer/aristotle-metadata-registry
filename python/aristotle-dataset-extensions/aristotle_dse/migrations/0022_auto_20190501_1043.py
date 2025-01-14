# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-01 00:43
from __future__ import unicode_literals

from django.db import migrations
from aristotle_mdr.utils.migrations import CustomFieldMover


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0057_auto_20190329_1609'),
        ('aristotle_dse', '0021_auto_20190415_0012'),
        ('aristotle_mdr_custom_fields', '0002_auto_20190212_1805'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        CustomFieldMover(
            app_label="aristotle_dse",
            model_name="DataSetSpecification",
            field_name="implementation_start_date",
            custom_field_name="Implementation Start Date",
            custom_field_type="date",
            custom_field_kwargs={"order": 0},
        ),
        CustomFieldMover(
            app_label="aristotle_dse",
            model_name="DataSetSpecification",
            field_name="implementation_end_date",
            custom_field_name="Implementation End Date",
            custom_field_type="date",
            custom_field_kwargs={"order": 1},
        ),
    ]
    