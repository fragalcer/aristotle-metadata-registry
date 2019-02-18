# -*- coding: utf-8 -*-
# Generated by Django 1.11.18 on 2019-02-12 09:35
from __future__ import unicode_literals

import aristotle_mdr.fields
import ckeditor_uploader.fields
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0020_auto_20190206_1930'),
        ('aristotle_mdr', '0050_auto_20190204_2227'),
        ('comet', '0005_auto_20181107_0433'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndicatorDenominatorDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(help_text='The position of this data element in the indicator', verbose_name='Order')),
                ('description', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('guide_for_use', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('data_element', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement')),
                ('data_set', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.Dataset')),
                ('data_set_specification', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IndicatorDisaggregationDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(help_text='The position of this data element in the indicator', verbose_name='Order')),
                ('description', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('guide_for_use', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('data_element', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement')),
                ('data_set', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.Dataset')),
                ('data_set_specification', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IndicatorInclusion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(help_text='The position of this indicator in the set', verbose_name='Order')),
                ('name', models.CharField(blank=True, help_text='The name identifying this indicator in the set', max_length=1024)),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='IndicatorNumeratorDefinition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(help_text='The position of this data element in the indicator', verbose_name='Order')),
                ('description', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('guide_for_use', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('data_element', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement')),
                ('data_set', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.Dataset')),
                ('data_set_specification', aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
        ),
        migrations.RenameField(
            model_name='indicator',
            old_name='computationDescription',
            new_name='computation_description',
        ),
        migrations.RemoveField(
            model_name='indicator',
            name='dataElementConcept',
        ),
        migrations.RemoveField(
            model_name='indicator',
            name='valueDomain',
        ),
        migrations.AddField(
            model_name='indicator',
            name='computation',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AlterField(
            model_name='indicator',
            name='denominator_description',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AlterField(
            model_name='indicator',
            name='numerator_description',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.AddField(
            model_name='indicatornumeratordefinition',
            name='indicator',
            field=aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, to='comet.Indicator'),
        ),
        migrations.AddField(
            model_name='indicatorinclusion',
            name='indicator',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='comet.Indicator'),
        ),
        migrations.AddField(
            model_name='indicatorinclusion',
            name='indicator_set',
            field=aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, to='comet.IndicatorSet'),
        ),
        migrations.AddField(
            model_name='indicatordisaggregationdefinition',
            name='indicator',
            field=aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, to='comet.Indicator'),
        ),
        migrations.AddField(
            model_name='indicatordenominatordefinition',
            name='indicator',
            field=aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, to='comet.Indicator'),
        ),
        migrations.AddField(
            model_name='indicator',
            name='benchmark',
            field=ckeditor_uploader.fields.RichTextUploadingField(blank=True),
        ),
        migrations.RenameModel(
            old_name='IndicatorType',
            new_name='IndicatorTypeOld',
        ),
        migrations.RenameModel(
            old_name='IndicatorSetType',
            new_name='IndicatorSetTypeOld',
        ),

        migrations.CreateModel(
            name='IndicatorType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid1, editable=False, help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries', unique=True)),
                ('name', aristotle_mdr.fields.ShortTextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)', verbose_name='definition')),
                ('stewardship_organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.StewardOrganisation', to_field='uuid')),
            ],
            options={
                'verbose_name': 'Indicator Type',
            },
        ),

        migrations.CreateModel(
            name='IndicatorSetType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('uuid', models.UUIDField(default=uuid.uuid1, editable=False, help_text='Universally-unique Identifier. Uses UUID1 as this improves uniqueness and tracking between registries', unique=True)),
                ('name', aristotle_mdr.fields.ShortTextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)', verbose_name='definition')),
                ('stewardship_organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.StewardOrganisation', to_field='uuid')),
            ],
            options={
                'abstract': False,
            },
        ),

        # migrations.AlterField(
        #     model_name='indicator',
        #     name='indicatorType',
        #     field=models.IntegerField(null=True),
        #     preserve_default=False,
        # ),
        # migrations.AlterField(
        #     model_name='indicatorset',
        #     name='indicatorSetType',
        #     field=models.IntegerField(null=True),
        #     preserve_default=False,
        # ),

        migrations.AddField(
            model_name='indicator',
            name='indicator_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='comet.IndicatorType'),
        ),
        migrations.AddField(
            model_name='indicatorset',
            name='indicator_set_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='comet.IndicatorSetType'),
        ),

    ]
