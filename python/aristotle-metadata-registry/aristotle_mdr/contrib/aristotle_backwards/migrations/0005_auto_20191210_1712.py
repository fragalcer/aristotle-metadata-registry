# Generated by Django 2.2.7 on 2019-12-10 23:12

import ckeditor_uploader.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_backwards', '0004_auto_20190503_1505'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classificationscheme',
            name='classificationStructure',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True, verbose_name='Classification Structure'),
        ),
    ]