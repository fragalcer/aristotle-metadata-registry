# Generated by Django 2.2.6 on 2019-10-14 00:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0079_auto_20190918_1610'),
    ]

    operations = [
        migrations.AddField(
            model_name='permissiblevalue',
            name='value_meaning_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='supplementaryvalue',
            name='value_meaning_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
