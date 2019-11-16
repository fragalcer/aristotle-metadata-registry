# Generated by Django 2.2.6 on 2019-11-11 01:10

import aristotle_mdr.fields
import ckeditor_uploader.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aristotle_mdr', '0075_auto_20190916_1602'),
    ]
    replaces = [
        ('mallard_qr', '0001_squashed_0005_fix_concept_fields'),
        ('mallard_qr', '0002_administrationmode_uuid'),
        ('mallard_qr', '0003_auto_20170823_0355'),
        ('mallard_qr', '0004_auto_20181107_0433'),
        ('mallard_qr', '0005_auto_20190502_1036'),
        ('mallard_qr', '0006_auto_20190503_1505'),
        ('mallard_qr', '0007_auto_20190604_1201'),
        ('mallard_qr', '0008_auto_20190809_1241'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdministrationMode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid1, editable=False, help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries', unique=True)),
                ('name', aristotle_mdr.fields.ShortTextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(blank=True, default='', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)', verbose_name='definition')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('_concept_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='aristotle_mdr._concept')),
                ('question_text', ckeditor_uploader.fields.RichTextUploadingField(blank=True, help_text='The text which describes the information which is to be obtained.')),
                ('instruction_text', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('estimated_seconds_response_time', models.PositiveIntegerField(blank=True, help_text='The estimated amount of time required to answer a question expressed in seconds.', null=True)),
                ('collected_data_element', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='aristotle_mdr.DataElement')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='ResponseDomain',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('maximum_occurrences', models.PositiveIntegerField(default=1, help_text='The maximum number of times a response can be included in a question')),
                ('minimum_occurrences', models.PositiveIntegerField(default=1, help_text='The minimum number of times a response can be included in a question')),
                ('blank_is_missing_value', models.BooleanField(default=False, help_text='When value is true a blank or empty variable content should be treated as a missing value.')),
                ('order', models.PositiveSmallIntegerField(blank=True, help_text='If a dataset is ordered, this indicates which position this item is in a dataset.', null=True, verbose_name='Position')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='response_domains', to='mallard_qr.Question')),
                ('value_domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ValueDomain')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
