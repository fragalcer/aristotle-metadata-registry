# Generated by Django 2.2.5 on 2019-10-24 06:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0047_remove_temp_field'),
    ]

    operations = [
        migrations.RenameField(
            model_name='distributiondataelementpath',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='dssclusterinclusion',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='dssdeinclusion',
            old_name='uuid',
            new_name='id',
        ),
        migrations.RenameField(
            model_name='dssgrouping',
            old_name='uuid',
            new_name='id',
        ),
    ]