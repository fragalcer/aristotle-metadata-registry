# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields
import ckeditor_uploader.fields


class Migration(migrations.Migration):

    replaces = [('comet', '0001_initial'), ('comet', '0002_auto_20150730_1153'), ('comet', '0003_indicator_outcomearea'), ('comet', '0004_auto_20160227_1732'), ('comet', '0005_auto_20160227_2258'), ('comet', '0006_auto_20160314_1629'), ('comet', '0007_promote_framework_to_concept'), ('comet', '0008_fix_concept_fields')]

    dependencies = [
        ('aristotle_mdr', '0001_squashed_0017_add_organisations'),
    ]

    operations = [
        migrations.CreateModel(
            name='Framework',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='Indicator',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('numerator_description', models.TextField(blank=True)),
                ('numerator_computation', models.TextField(blank=True)),
                ('denominator_description', models.TextField(blank=True)),
                ('denominator_computation', models.TextField(blank=True)),
                ('computationDescription', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('rationale', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('disaggregation_description', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('dataElementConcept', models.ForeignKey(verbose_name='Data Element Concept', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElementConcept', null=True)),
                ('denominators', models.ManyToManyField(related_name='as_demoninator', to='aristotle_mdr.DataElement', blank=True)),
                ('disaggregators', models.ManyToManyField(related_name='as_disaggregator', to='aristotle_mdr.DataElement', blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='IndicatorSet',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='IndicatorSetType',
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
            name='IndicatorType',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='OutcomeArea',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='QualityStatement',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('timeliness', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('accessibility', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('interpretability', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('relevance', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('accuracy', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('coherence', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('implementationStartDate', models.DateField(null=True, blank=True)),
                ('implementationEndDate', models.DateField(null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.AddField(
            model_name='indicatorset',
            name='indicatorSetType',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='comet.IndicatorSetType', null=True),
        ),
        migrations.AddField(
            model_name='indicatorset',
            name='indicators',
            field=models.ManyToManyField(related_name='indicatorSets', null=True, to='comet.Indicator', blank=True),
        ),
        migrations.AddField(
            model_name='indicator',
            name='indicatorType',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='comet.IndicatorType', null=True),
        ),
        migrations.AddField(
            model_name='indicator',
            name='numerators',
            field=models.ManyToManyField(related_name='as_numerator', to='aristotle_mdr.DataElement', blank=True),
        ),
        migrations.AddField(
            model_name='indicator',
            name='outcome_areas',
            field=models.ManyToManyField(related_name='indicators', null=True, to='comet.OutcomeArea', blank=True),
        ),
        migrations.AddField(
            model_name='indicator',
            name='valueDomain',
            field=models.ForeignKey(verbose_name='Value Domain', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueDomain', null=True),
        ),
        migrations.AddField(
            model_name='framework',
            name='indicators',
            field=models.ManyToManyField(related_name='frameworks', null=True, to='comet.Indicator', blank=True),
        ),
        migrations.AddField(
            model_name='framework',
            name='parentFramework',
            field=models.ForeignKey(related_name='childFrameworks', blank=True, on_delete=django.db.models.deletion.CASCADE, to='comet.Framework', null=True),
        ),
    ]
