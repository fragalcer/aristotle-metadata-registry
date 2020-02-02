# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0020_add_uuids'),
    ]

    operations = [
        migrations.CreateModel(
            name='GlossaryAdditionalDefinition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('definition', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='GlossaryItem',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('index', models.ManyToManyField(related_name='related_glossary_items', null=True, to='aristotle_mdr._concept', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.AddField(
            model_name='glossaryadditionaldefinition',
            name='glossaryItem',
            field=models.ForeignKey(related_name='alternate_definitions', on_delete=django.db.models.deletion.CASCADE, to='aristotle_glossary.GlossaryItem'),
        ),
        migrations.AddField(
            model_name='glossaryadditionaldefinition',
            name='registrationAuthority',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.RegistrationAuthority'),
        ),
        migrations.AlterUniqueTogether(
            name='glossaryadditionaldefinition',
            unique_together=set([('glossaryItem', 'registrationAuthority')]),
        ),
    ]
