# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_help', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='helpbase',
            name='is_public',
            field=models.BooleanField(default=True, help_text='Indicates if a help topic is available to non-registered users.'),
        ),
    ]
