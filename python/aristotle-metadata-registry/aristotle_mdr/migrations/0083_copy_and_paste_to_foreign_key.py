# Generated by Django 2.2.6 on 2019-10-15 06:22

from django.db import migrations
from aristotle_mdr.utils.migration_utils import data_copy_and_paste


def duplicate_models_foreign_keys(apps, schema_editor):
    PermissibleValue = apps.get_model('aristotle_mdr', 'permissiblevalue')
    SupplementaryValue = apps.get_model('aristotle_mdr', 'supplementaryvalue')
    data_copy_and_paste(PermissibleValue, 'value_meaning_new', 'value_meaning_id')
    data_copy_and_paste(SupplementaryValue, 'value_meaning_new', 'value_meaning_id')


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0082_auto_20191015_0617'),
    ]

    operations = [
        migrations.RunPython(duplicate_models_foreign_keys, reverse_code=migrations.RunPython.noop),
    ]
