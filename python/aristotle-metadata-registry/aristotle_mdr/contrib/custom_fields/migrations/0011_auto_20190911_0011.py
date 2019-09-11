# Generated by Django 2.2.5 on 2019-09-11 05:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_custom_fields', '0010_auto_20190910_2110'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfield',
            name='system_name',
            field=models.CharField(help_text='A name used for uniquely identifying the custom field', max_length=1000, null=True, unique=True),
        ),
    ]
