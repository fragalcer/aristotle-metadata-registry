# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0013_now_with_dcat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='accrual_periodicity',
            field=models.TextField(help_text='The frequency at which dataset is published.', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='byte_size',
            field=models.TextField(help_text='The size in bytes can be approximated when the precise size is not known.', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='format_type',
            field=models.CharField(help_text='The file format of the distribution.', max_length=512, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='media_type',
            field=models.CharField(help_text='The media type of the distribution as defined by IANA.', max_length=512, null=True, blank=True),
        ),
    ]
