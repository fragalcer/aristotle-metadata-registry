# Generated by Django 2.2.4 on 2019-09-18 06:11

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_links', '0011_generate_uuids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationrole',
            name='uuid',
            field=models.UUIDField(
                default=uuid.uuid1,
                editable=False,
                help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries',
                unique=True
            ),
        ),
    ]
