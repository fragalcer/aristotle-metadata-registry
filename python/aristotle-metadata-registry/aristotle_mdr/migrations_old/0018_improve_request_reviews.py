# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0017_add_organisations'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewrequest',
            name='cascade_registration',
            field=models.IntegerField(default=0, help_text='Update the registration of associated items', choices=[(0, 'No'), (1, 'Yes')]),
        ),
        migrations.AddField(
            model_name='reviewrequest',
            name='registration_date',
            field=models.DateField(default='1970-01-01', help_text='date and time you want the metadata to be registered from', verbose_name='Date registration effective'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='reviewrequest',
            name='message',
            field=models.TextField(help_text='An optional message accompanying a request, this will accompany the approved registration status', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='reviewrequest',
            name='state',
            field=models.IntegerField(default=0, help_text='The state at which a user wishes a metadata item to be endorsed', choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')]),
            preserve_default=False,
        ),
    ]
