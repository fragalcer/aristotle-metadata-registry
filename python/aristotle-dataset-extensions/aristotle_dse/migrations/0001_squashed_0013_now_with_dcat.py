# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models
from django.db import migrations, models
import ckeditor_uploader.fields


class Migration(migrations.Migration):

    replaces = [('aristotle_dse', '0001_initial'), ('aristotle_dse', '0002_auto_20150510_0249'), ('aristotle_dse', '0003_add_clusters_improve_names'), ('aristotle_dse', '0004_auto_20160103_0200'), ('aristotle_dse', '0005_improve_inculsion_help_text'), ('aristotle_dse', '0006_auto_20160103_1855'), ('aristotle_dse', '0007_add_ordering_to_inclusions'), ('aristotle_dse', '0008_auto_20160318_2335'), ('aristotle_dse', '0009_auto_20160725_1958'), ('aristotle_dse', '0010_datasource_specification'), ('aristotle_dse', '0011_auto_20160726_2015'), ('aristotle_dse', '0012_fix_concept_fields'), ('aristotle_dse', '0013_now_with_dcat')]

    dependencies = [
        ('aristotle_mdr_identifiers', '0001_initial'),
        ('aristotle_mdr', '0001_squashed_0017_add_organisations'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataCatalog',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('issued', models.DateField(help_text='Date of formal issuance (e.g., publication) of the catalog.', null=True, blank=True)),
                ('dct_modified', models.DateTimeField(help_text='Most recent date on which the catalog was changed, updated or modified.', null=True, blank=True)),
                ('homepage', models.URLField(help_text='The dataset specification to which this data source conforms', null=True, blank=True)),
                ('spatial', models.TextField(help_text='The geographical area covered by the catalog.', null=True, blank=True)),
                ('license', models.TextField(help_text='This links to the license document under which the catalog is made available and not the datasets. Even if the license of the catalog applies to all of its datasets and distributions, it should be replicated on each distribution.', null=True, blank=True)),
                ('publisher', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Organization', help_text='The entity responsible for making the catalog online.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('issued', models.DateField(help_text='Date of formal issuance (e.g., publication) of the catalog.', null=True, blank=True)),
                ('accrual_periodicity', models.TextField(help_text='\tThe frequency at which dataset is published.', null=True, blank=True)),
                ('spatial', models.TextField(help_text='Spatial coverage of the dataset.', null=True, blank=True)),
                ('temporal', models.TextField(help_text='The temporal period that the dataset covers.', null=True, blank=True)),
                ('landing_page', models.URLField(help_text='A Web page that can be navigated to in a Web browser to gain access to the dataset, its distributions and/or additional information', null=True, blank=True)),
                ('contact_point', models.TextField(help_text='The temporal period that the dataset covers.', null=True, blank=True)),
                ('dct_modified', models.DateTimeField(help_text='Most recent date on which the catalog was changed, updated or modified.', null=True, blank=True)),
                ('catalog', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataCatalog', help_text='An entity responsible for making the dataset available.', null=True)),
                ('publisher', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Organization', help_text='An entity responsible for making the dataset available.', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DataSetSpecification',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('ordered', models.BooleanField(default=False, help_text='Indicates if the ordering for a dataset is must match exactly the order laid out in the specification.')),
                ('collection_method', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('implementation_start_date', models.DateField(null=True, blank=True)),
                ('implementation_end_date', models.DateField(null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='Distribution',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept')),
                ('issued', models.DateField(help_text='Date of formal issuance (e.g., publication) of the catalog.', null=True, blank=True)),
                ('dct_modified', models.DateTimeField(help_text='Most recent date on which the catalog was changed, updated or modified.', null=True, blank=True)),
                ('license', models.TextField(help_text='This links to the license document under which the distribution is made available.', null=True, blank=True)),
                ('rights', models.TextField(help_text='Information about rights held in and over the distribution.', null=True, blank=True)),
                ('access_URL', models.URLField(help_text='A landing page, feed, SPARQL endpoint or other type of resource that gives access to the distribution of the dataset.', null=True, blank=True)),
                ('download_URL', models.URLField(help_text='A file that contains the distribution of the dataset in a given format.', null=True, blank=True)),
                ('byte_size', models.TextField(help_text='The size in bytes can be approximated when the precise size is not known.')),
                ('media_type', models.CharField(help_text='The media type of the distribution as defined by IANA.', max_length=512)),
                ('format_type', models.CharField(help_text='The file format of the distribution.', max_length=512)),
                ('publisher', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Organization', help_text='An entity responsible for making the dataset available.', null=True)),
                ('specification', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification', help_text='The dataset specification to which this data source conforms', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DistributionDataElementPath',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('logical_path', models.CharField(help_text='A text expression that specifies how to identify which series of data in the distribution maps to this data element', max_length=256)),
                ('order', models.PositiveSmallIntegerField(help_text='Column position within a dataset.', null=True, verbose_name='Position', blank=True)),
                ('data_element', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement', help_text='An entity responsible for making the dataset available.', null=True)),
                ('distribution', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.Distribution', help_text='A relation to the DCAT Distribution Record.', null=True)),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='DSSClusterInclusion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('maximum_occurances', models.PositiveIntegerField(default=1, help_text='The maximum number of times a item can be included in a dataset')),
                ('cardinality', models.CharField(default='conditional', help_text='Specifies if a field is required, optional or conditional within a dataset based on this specification.', max_length=20, choices=[('optional', 'Optional'), ('conditional', 'Conditional'), ('mandatory', 'Mandatory')])),
                ('specific_information', ckeditor_uploader.fields.RichTextUploadingField(help_text='Any additional information on the inclusion of a data element or cluster in a dataset.', blank=True)),
                ('conditional_obligation', models.TextField(help_text='If an item is present conditionally, this field defines the conditions under which an item will appear.', blank=True)),
                ('order', models.PositiveSmallIntegerField(help_text='If a dataset is ordered, this indicates which position this item is in a dataset.', null=True, verbose_name='Position', blank=True)),
                ('child', models.ForeignKey(related_name='parent_dss', on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
                ('dss', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
                'verbose_name': 'DSS Cluster Inclusion',
            },
        ),
        migrations.CreateModel(
            name='DSSDEInclusion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('maximum_occurances', models.PositiveIntegerField(default=1, help_text='The maximum number of times a item can be included in a dataset')),
                ('cardinality', models.CharField(default='conditional', help_text='Specifies if a field is required, optional or conditional within a dataset based on this specification.', max_length=20, choices=[('optional', 'Optional'), ('conditional', 'Conditional'), ('mandatory', 'Mandatory')])),
                ('specific_information', ckeditor_uploader.fields.RichTextUploadingField(help_text='Any additional information on the inclusion of a data element or cluster in a dataset.', blank=True)),
                ('conditional_obligation', models.TextField(help_text='If an item is present conditionally, this field defines the conditions under which an item will appear.', blank=True)),
                ('order', models.PositiveSmallIntegerField(help_text='If a dataset is ordered, this indicates which position this item is in a dataset.', null=True, verbose_name='Position', blank=True)),
                ('data_element', models.ForeignKey(related_name='dssInclusions', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement')),
                ('dss', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.DataSetSpecification')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
                'verbose_name': 'DSS Data Element Inclusion',
            },
        ),
        migrations.AddField(
            model_name='datasetspecification',
            name='clusters',
            field=models.ManyToManyField(to='aristotle_dse.DataSetSpecification', null=True, through='aristotle_dse.DSSClusterInclusion', blank=True),
        ),
        migrations.AddField(
            model_name='datasetspecification',
            name='data_elements',
            field=models.ManyToManyField(to='aristotle_mdr.DataElement', null=True, through='aristotle_dse.DSSDEInclusion', blank=True),
        ),
        migrations.AddField(
            model_name='datasetspecification',
            name='statistical_unit',
            field=models.ForeignKey(related_name='statistical_unit_of', blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', help_text='Indiciates if the ordering for a dataset is must match exactly the order laid out in the specification.', null=True),
        ),
        migrations.AddField(
            model_name='distribution',
            name='dataset',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_dse.Dataset', help_text='Connects a distribution to its available datasets', null=True),
        ),
    ]
