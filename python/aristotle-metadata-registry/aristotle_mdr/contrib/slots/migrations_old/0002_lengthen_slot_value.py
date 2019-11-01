# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_slots', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slot',
            name='value',
            field=models.TextField(),
        ),
    ]
