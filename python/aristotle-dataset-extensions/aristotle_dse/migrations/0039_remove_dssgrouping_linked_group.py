# Generated by Django 2.2.5 on 2019-10-09 01:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0038_copy_paste_data_from_old_through_table_to_new'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dssgrouping',
            name='linked_group',
        ),
    ]