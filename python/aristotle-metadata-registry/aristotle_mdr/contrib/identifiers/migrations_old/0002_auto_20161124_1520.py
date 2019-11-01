# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_identifiers', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scopedidentifier',
            name='version',
            field=models.CharField(help_text='unique version identifier of the Scoped_Identifier which identifies an Item', default='', max_length=512, blank=True),
        ),
    ]
