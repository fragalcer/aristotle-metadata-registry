# Generated by Django 2.2.5 on 2019-10-24 06:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0084_remove_temp_field'),
    ]

    operations = [
        migrations.RenameField(
            model_name='dedderivesthrough',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='dedinputsthrough',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='permissiblevalue',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='supplementaryvalue',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='valuemeaning',
            old_name='uuid',
            new_name='id',
        ),
    ]
