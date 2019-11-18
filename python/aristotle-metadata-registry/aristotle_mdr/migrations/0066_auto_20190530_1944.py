# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-31 00:44
from __future__ import unicode_literals

import django.db.models
import aristotle_mdr.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0065_auto_20190529_1048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='possumprofile',
            name='profilePicture',
            field=aristotle_mdr.fields.ConvertedConstrainedImageField(blank=True, content_types=['image/jpg', 'image/png', 'image/bmp', 'image/jpeg', 'image/x-ms-bmp'], height_field='profilePictureHeight', js_checker=True, max_upload_size=10485760, mime_lookup_length=4096, null=True, upload_to='', width_field='profilePictureWidth'),
        ),
    ]