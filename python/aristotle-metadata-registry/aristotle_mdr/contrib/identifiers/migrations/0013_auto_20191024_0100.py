# Generated by Django 2.2.5 on 2019-10-24 06:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_identifiers', '0012_make_uuid_field_the_pk'),
    ]

    operations = [
        migrations.RenameField(
            model_name='scopedidentifier',
            old_name='uuid',
            new_name='id',
        ),
    ]