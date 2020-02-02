# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0031_auto_20180629_0143'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationauthority',
            name='new_active',
            field=models.IntegerField(choices=[(0, 'Active & Visible'), (1, 'Inactive & Visible'), (2, 'Inactive & Hidden')], default=0, help_text='<div id="active-alert" class="alert alert-warning" role="alert">Setting this to Inactive will disable all further registration actions</div>'),
        )
    ]
