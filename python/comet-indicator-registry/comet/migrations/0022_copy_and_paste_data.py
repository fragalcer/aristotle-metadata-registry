from django.db import migrations
from aristotle_mdr.utils.migration_utils import data_copy_and_paste


def duplicate_model_foreign_key(apps, schema_editor):
    FrameworkDimension = apps.get_model('comet', 'frameworkdimension')
    data_copy_and_paste(FrameworkDimension, 'parent', 'parent_new')


def duplicate_model_foreign_key_reverse(apps, schema_editor):
    FrameworkDimension = apps.get_model('comet', 'frameworkdimension')
    data_copy_and_paste(FrameworkDimension, 'parent_new', 'parent')


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0021_frameworkdimension_parent_new'),
    ]

    operations = [
        migrations.RunPython(duplicate_model_foreign_key, reverse_code=duplicate_model_foreign_key_reverse),
    ]
