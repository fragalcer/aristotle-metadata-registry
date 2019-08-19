# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0017_add_organisations'),
    ]

    operations = [
        migrations.CreateModel(
            name='Namespace',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('shorthand_prefix', models.CharField(help_text='prefix conventionally used as shorthand for a namespace, for greater readability, in text for human consumption.', max_length=512)),
                ('naming_authority', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Organization')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScopedIdentifier',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('identifier', models.CharField(help_text='String used to unambiguously denote an Item within the scope of a specified Namespace.', max_length=512)),
                ('version', models.CharField(default=b'', help_text='unique version identifier of the Scoped_Identifier which identifies an Item', max_length=512, blank=True)),
                ('concept', models.ForeignKey(related_name='identifiers', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('namespace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_identifiers.Namespace')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='scopedidentifier',
            unique_together=set([('namespace', 'identifier', 'version')]),
        ),
    ]
