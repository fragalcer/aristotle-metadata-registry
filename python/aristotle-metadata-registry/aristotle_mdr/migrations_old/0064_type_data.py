from django.db import migrations

from aristotle_mdr.utils.cache import recache_types


def add_type_data(apps, schema_migration):
    labels = recache_types(apps)


def remove_type_data(apps, schema_migration):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0063_auto_20190515_1942')
    ]

    operations = [
        migrations.RunPython(add_type_data, remove_type_data)
    ]
