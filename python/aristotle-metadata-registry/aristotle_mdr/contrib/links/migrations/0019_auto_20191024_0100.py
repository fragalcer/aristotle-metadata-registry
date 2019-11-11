# Generated by Django 2.2.5 on 2019-10-24 06:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_links', '0018_remove_temp_field'),
    ]

    operations = [
        migrations.RenameField(
            model_name='relationrole',
            old_name='uuid',
            new_name='id',
        ),
        migrations.AlterField(
            model_name='linkend',
            name='role',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_links.RelationRole'),
        ),
    ]
