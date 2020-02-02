# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr_links', '0002_auto_20170208_1819'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationrole',
            name='multiplicity',
            field=models.PositiveIntegerField(help_text='number of links which must (logically) be members of the source relation of this role, differing only by an end with this role as an end_role.', blank=True, null=True),
        ),
    ]
