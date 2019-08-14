# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields
import ckeditor_uploader.fields


class Migration(migrations.Migration):

    replaces = [('mallard_qr', '0001_initial'), ('mallard_qr', '0002_auto_20160621_2105'), ('mallard_qr', '0003_auto_20160703_0540'), ('mallard_qr', '0004_remove_question_response_domain'), ('mallard_qr', '0005_fix_concept_fields')]

    dependencies = [
        ('aristotle_mdr', '0001_squashed_0017_add_organisations'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdministrationMode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)', verbose_name='definition')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('question_text', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('instruction_text', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('estimated_seconds_response_time', models.PositiveIntegerField(help_text='he estimated amount of time required to answer a question expressed in seconds.', null=True, blank=True)),
                ('collected_data_element', models.ForeignKey(related_name='questions', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='ResponseDomain',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('maximum_occurances', models.PositiveIntegerField(default=1, help_text='The maximum number of times a response can be included in a question')),
                ('minimum_occurances', models.PositiveIntegerField(default=1, help_text='The minimum number of times a response can be included in a question')),
                ('blank_is_missing_value', models.BooleanField(default=False, help_text='When value is true a blank or empty variable content should be treated as a missing value.')),
                ('order', models.PositiveSmallIntegerField(help_text='If a dataset is ordered, this indicates which position this item is in a dataset.', null=True, verbose_name='Position', blank=True)),
                ('question', models.ForeignKey(related_name='response_domains', on_delete=django.db.models.deletion.CASCADE, to='mallard_qr.Question')),
                ('value_domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueDomain')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
