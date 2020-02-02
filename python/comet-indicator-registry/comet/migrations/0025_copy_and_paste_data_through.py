from django.db import migrations
from aristotle_mdr.utils.migration_utils import data_copy_and_paste_from_m2m_through_model


def copy_and_paste_data_from_old_through_table_to_new(apps, schema_editor):
    indicator_model = apps.get_model('comet', 'indicator')
    through_model = apps.get_model('comet', 'indicatorframeworkdimensionsthrough')
    data_copy_and_paste_from_m2m_through_model(indicator_model, through_model, 'dimensions')


def copy_and_paste_data_from_new_through_table_to_old(apps, schema_editor):
    indicator_model = apps.get_model('comet', 'indicator')
    through_model = apps.get_model('comet', 'indicator_dimensions')
    data_copy_and_paste_from_m2m_through_model(indicator_model, through_model, 'dimensions_new')


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0024_create_indicator_dimension_through'),
    ]

    operations = [
        migrations.RunPython(copy_and_paste_data_from_old_through_table_to_new, reverse_code=copy_and_paste_data_from_new_through_table_to_old),
    ]
