# Generated by Django 2.2.5 on 2019-10-16 04:44

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_identifiers', '0011_auto_20190918_1611'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scopedidentifier',
            name='id',
        ),
        migrations.AlterField(
            model_name='scopedidentifier',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid1, editable=False, help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries', primary_key=True, serialize=False, unique=True),
        ),
    ]