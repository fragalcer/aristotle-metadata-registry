# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import ckeditor_uploader.fields
import django.utils.timezone
from django.conf import settings
import model_utils.fields


class Migration(migrations.Migration):

    replaces = [
        ('aristotle_mdr', '0001_initial'),
        ('aristotle_mdr', '0002_auto_20150409_0656'),
        ('aristotle_mdr', '0003_auto_20150416_0024'),
        ('aristotle_mdr', '0004_auto_20150424_0059'),
        ('aristotle_mdr', '0005_auto_20150526_1058'),
        ('aristotle_mdr', '0006_remove_status_indictionary'),
        ('aristotle_mdr', '0007_rename_description_fields'),
        ('aristotle_mdr', '0008_auto_20151216_0339'),
        ('aristotle_mdr', '0009_add_explicit_related_name_for_values'),
        ('aristotle_mdr', '0010_auto_20160106_1814'),
        ('aristotle_mdr', '0011_update_ckeditor_remove_d19_errors'),
        ('aristotle_mdr', '0012_better_workflows'),
        ('aristotle_mdr', '0013_concept_field_fixer_part1'),
        ('aristotle_mdr', '0014_concept_field_fixer_part2'),
        ('aristotle_mdr', '0015_concept_field_fixer_part3'),
        ('aristotle_mdr', '0016_auto_20160919_1939'),
        ('aristotle_mdr', '0017_add_organisations'),
    ]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='_concept',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(verbose_name='definition', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)')),
                ('_is_public', models.BooleanField(default=False)),
                ('_is_locked', models.BooleanField(default=False)),
                ('short_name', models.CharField(max_length=100, blank=True)),
                ('version', models.CharField(max_length=20, blank=True)),
                ('synonyms', models.CharField(max_length=200, blank=True)),
                ('references', ckeditor_uploader.fields.RichTextUploadingField(blank=True)),
                ('origin_URI', models.URLField(blank=True, help_text='If imported, the original location of the item')),
                ('comments', ckeditor_uploader.fields.RichTextUploadingField(blank=True, help_text='Descriptive comments about the metadata item (8.1.2.2.3.4)')),
                ('submitting_organisation', models.CharField(max_length=256, blank=True)),
                ('responsible_organisation', models.CharField(max_length=256, blank=True)),
            ],
            options={
                'verbose_name': 'item',
            },
        ),
        migrations.CreateModel(
            name='DiscussionComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('body', models.TextField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created'],
            },
        ),
        migrations.CreateModel(
            name='DiscussionPost',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('body', models.TextField()),
                ('title', models.CharField(max_length=256)),
                ('closed', models.BooleanField(default=False)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-modified'],
            },
        ),
        migrations.CreateModel(
            name='Measure',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(verbose_name='definition', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(verbose_name='definition', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)')),
                ('uri', models.URLField(blank=True, null=True, help_text='uri for Organization')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PermissibleValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('value', models.CharField(max_length=32, help_text='the actual value of the Value')),
                ('meaning', models.CharField(max_length=255, help_text="A textual designation of a value, where a relation to a Value meaning doesn't exist")),
                ('order', models.PositiveSmallIntegerField(verbose_name='Position')),
                ('start_date', models.DateField(blank=True, null=True, help_text='Date at which the value became valid')),
                ('end_date', models.DateField(blank=True, null=True, help_text='Date at which the value ceased to be valid')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PossumProfile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            name='ReviewRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('message', models.TextField(blank=True, null=True, help_text='An optional message accompanying a request')),
                ('response', models.TextField(blank=True, null=True, help_text='An optional message responding to a request')),
                ('status', models.IntegerField(choices=[(0, 'Submitted'), (5, 'Cancelled'), (10, 'Accepted'), (15, 'Rejected')], default=0, help_text='Status of a review')),
                ('state', models.IntegerField(blank=True, choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], null=True, help_text='The state at which a user wishes a metadata item to be endorsed')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Status',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('changeDetails', models.TextField(blank=True, null=True)),
                ('state', models.IntegerField(choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], default=1, help_text='Designation (3.2.51) of the status in the registration life-cycle of an Administered_Item')),
                ('registrationDate', models.DateField(verbose_name='Date registration effective', help_text='date and time an Administered_Item became/becomes available to registry users')),
                ('until_date', models.DateField(verbose_name='Date registration expires', blank=True, null=True, help_text='date and time the Registration of an Administered_Item by a Registration_Authority in a registry is no longer effective')),
            ],
            options={
                'verbose_name_plural': 'Statuses',
            },
        ),
        migrations.CreateModel(
            name='SupplementaryValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('value', models.CharField(max_length=32, help_text='the actual value of the Value')),
                ('meaning', models.CharField(max_length=255, help_text="A textual designation of a value, where a relation to a Value meaning doesn't exist")),
                ('order', models.PositiveSmallIntegerField(verbose_name='Position')),
                ('start_date', models.DateField(blank=True, null=True, help_text='Date at which the value became valid')),
                ('end_date', models.DateField(blank=True, null=True, help_text='Date at which the value ceased to be valid')),
            ],
            options={
                'ordering': ['order'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ValueMeaning',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('meaning', models.CharField(max_length=255, help_text='The semantic content of a possible value (3.2.141)')),
                ('order', models.PositiveSmallIntegerField(verbose_name='Position')),
                ('start_date', models.DateField(blank=True, null=True, help_text='Date at which the value meaning became valid')),
                ('end_date', models.DateField(blank=True, null=True, help_text='Date at which the value meaning ceased to be valid')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='Workgroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', editable=False, default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', editable=False, default=django.utils.timezone.now)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', ckeditor_uploader.fields.RichTextUploadingField(verbose_name='definition', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)')),
                ('archived', models.BooleanField(verbose_name='Archived', default=False, help_text='Archived workgroups can no longer have new items or discussions created within them.')),
                ('managers', models.ManyToManyField(related_name='workgroup_manager_in', verbose_name='Managers', to=settings.AUTH_USER_MODEL, blank=True)),
                ('stewards', models.ManyToManyField(related_name='steward_in', verbose_name='Stewards', to=settings.AUTH_USER_MODEL, blank=True)),
                ('submitters', models.ManyToManyField(related_name='submitter_in', verbose_name='Submitters', to=settings.AUTH_USER_MODEL, blank=True)),
                ('viewers', models.ManyToManyField(related_name='viewer_in', verbose_name='Viewers', to=settings.AUTH_USER_MODEL, blank=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConceptualDomain',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.TextField(verbose_name='description', blank=True, help_text='Description or specification of a rule, reference, or range for a set of all value meanings for a Conceptual Domain')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DataElement',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DataElementConcept',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
                ('conceptualDomain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ConceptualDomain', blank=True, help_text='references a Conceptual_Domain that is part of the specification of the Data_Element_Concept', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DataElementDerivation',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
                ('derivation_rule', models.TextField(blank=True, help_text='text of a specification of a data element Derivation_Rule')),
                ('derives', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElement', blank=True, related_name='derived_from', help_text='binds with one or more output Data_Elements that are the result of the application of the Data_Element_Derivation.', null=True)),
                ('inputs', models.ManyToManyField(related_name='input_to_derivation', blank=True, to='aristotle_mdr.DataElement', help_text='binds one or more input Data_Element(s) with a Data_Element_Derivation.')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='DataType',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='ObjectClass',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'verbose_name_plural': 'Object Classes',
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='Property',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
                'verbose_name_plural': 'Properties',
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='RegistrationAuthority',
            fields=[
                ('organization_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Organization', serialize=False, auto_created=True, primary_key=True)),
                ('locked_state', models.IntegerField(choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], default=2)),
                ('public_state', models.IntegerField(choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], default=3)),
                ('notprogressed', models.TextField(blank=True)),
                ('incomplete', models.TextField(blank=True)),
                ('candidate', models.TextField(blank=True)),
                ('recorded', models.TextField(blank=True)),
                ('qualified', models.TextField(blank=True)),
                ('standard', models.TextField(blank=True)),
                ('preferred', models.TextField(blank=True)),
                ('superseded', models.TextField(blank=True)),
                ('retired', models.TextField(blank=True)),
                ('registrars', models.ManyToManyField(related_name='registrar_in', verbose_name='Registrars', to=settings.AUTH_USER_MODEL, blank=True)),
            ],
            options={
                'verbose_name_plural': 'Registration Authorities',
            },
            # Commented out as this is no longer true
            # See: https://stackoverflow.com/questions/33205279/django-migrations-refuse-to-acknowledge-a-model-no-longer-inherits-from-old-pare
            bases=('aristotle_mdr.organization',),
        ),
        migrations.CreateModel(
            name='UnitOfMeasure',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
                ('symbol', models.CharField(max_length=20, blank=True)),
                ('measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Measure', blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'Units Of Measure',
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='ValueDomain',
            fields=[
                ('_concept_ptr', models.OneToOneField(parent_link=True, on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', serialize=False, auto_created=True, primary_key=True)),
                ('format', models.CharField(max_length=100, blank=True, null=True, help_text='template for the structure of the presentation of the value(s)')),
                ('maximum_length', models.PositiveIntegerField(blank=True, null=True, help_text='maximum number of characters available to represent the Data Element value')),
                ('description', models.TextField(verbose_name='description', blank=True, help_text='Description or specification of a rule, reference, or range for a set of all values for a Value Domain.')),
                ('conceptual_domain', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ConceptualDomain', blank=True, help_text='The Conceptual Domain that this Value Domain which provides representation.', null=True)),
                ('data_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataType', blank=True, help_text='Datatype used in a Value Domain', null=True)),
                ('unit_of_measure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.UnitOfMeasure', blank=True, help_text='Unit of Measure used in a Value Domain', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.AddField(
            model_name='supplementaryvalue',
            name='value_meaning',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueMeaning', blank=True, help_text='A reference to the value meaning that this designation relates to', null=True),
        ),
        migrations.AddField(
            model_name='status',
            name='concept',
            field=models.ForeignKey(related_name='statuses', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept'),
        ),
        migrations.AddField(
            model_name='reviewrequest',
            name='concepts',
            field=models.ManyToManyField(related_name='review_requests', to='aristotle_mdr._concept'),
        ),
        migrations.AddField(
            model_name='reviewrequest',
            name='requester',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, related_name='requested_reviews', help_text='The user requesting a review'),
        ),
        migrations.AddField(
            model_name='reviewrequest',
            name='reviewer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, related_name='reviewed_requests', help_text='The user performing a review', null=True),
        ),
        migrations.AddField(
            model_name='possumprofile',
            name='favourites',
            field=models.ManyToManyField(related_name='favourited_by', blank=True, to='aristotle_mdr._concept'),
        ),
        migrations.AddField(
            model_name='possumprofile',
            name='savedActiveWorkgroup',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Workgroup', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='possumprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, related_name='profile'),
        ),
        migrations.AddField(
            model_name='permissiblevalue',
            name='value_meaning',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueMeaning', blank=True, help_text='A reference to the value meaning that this designation relates to', null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='managers',
            field=models.ManyToManyField(related_name='organization_manager_in', verbose_name='Managers', to=settings.AUTH_USER_MODEL, blank=True),
        ),
        migrations.AddField(
            model_name='discussionpost',
            name='relatedItems',
            field=models.ManyToManyField(related_name='relatedDiscussions', blank=True, to='aristotle_mdr._concept'),
        ),
        migrations.AddField(
            model_name='discussionpost',
            name='workgroup',
            field=models.ForeignKey(related_name='discussions', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Workgroup'),
        ),
        migrations.AddField(
            model_name='discussioncomment',
            name='post',
            field=models.ForeignKey(related_name='comments', on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DiscussionPost'),
        ),
        migrations.AddField(
            model_name='_concept',
            name='submitter',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, blank=True, related_name='created_items', help_text='This is the person who first created an item. Users can always see items they made.', null=True),
        ),
        migrations.AddField(
            model_name='_concept',
            name='superseded_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', blank=True, null=True, related_name='supersedes'),
        ),
        migrations.AddField(
            model_name='_concept',
            name='workgroup',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Workgroup', blank=True, null=True, related_name='items'),
        ),
        migrations.AddField(
            model_name='valuemeaning',
            name='conceptual_domain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ConceptualDomain'),
        ),
        migrations.AddField(
            model_name='supplementaryvalue',
            name='valueDomain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueDomain', related_name='supplementaryvalue_set', help_text='Enumerated Value Domain that this value meaning relates to'),
        ),
        migrations.AddField(
            model_name='status',
            name='registrationAuthority',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.RegistrationAuthority'),
        ),
        migrations.AddField(
            model_name='reviewrequest',
            name='registration_authority',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.RegistrationAuthority', help_text='The registration authority the requester wishes to endorse the metadata item'),
        ),
        migrations.AddField(
            model_name='permissiblevalue',
            name='valueDomain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueDomain', related_name='permissiblevalue_set', help_text='Enumerated Value Domain that this value meaning relates to'),
        ),
        migrations.AddField(
            model_name='dataelementconcept',
            name='objectClass',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ObjectClass', blank=True, help_text='references an Object_Class that is part of the specification of the Data_Element_Concept', null=True),
        ),
        migrations.AddField(
            model_name='dataelementconcept',
            name='property',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.Property', blank=True, help_text='references a Property that is part of the specification of the Data_Element_Concept', null=True),
        ),
        migrations.AddField(
            model_name='dataelement',
            name='dataElementConcept',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.DataElementConcept', verbose_name='Data Element Concept', blank=True, help_text='binds with a Value_Domain that describes a set of possible values that may be recorded in an instance of the Data_Element', null=True),
        ),
        migrations.AddField(
            model_name='dataelement',
            name='valueDomain',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr.ValueDomain', verbose_name='Value Domain', blank=True, help_text='binds with a Data_Element_Concept that provides the meaning for the Data_Element', null=True),
        ),
    ]
