# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-08-09 02:33
from __future__ import unicode_literals

import aristotle_mdr.fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0069_auto_20190801_1119'),
    ]

    operations = [
        migrations.AlterField(
            model_name='_concept',
            name='_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='contenttypes.ContentType'),
        ),
        migrations.AlterField(
            model_name='_concept',
            name='submitter',
            field=models.ForeignKey(blank=True, help_text='This is the person who first created an item. Users can always see items they made.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_items', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='_concept',
            name='workgroup',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='aristotle_mdr.Workgroup'),
        ),
        migrations.AlterField(
            model_name='dataelement',
            name='dataElementConcept',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='binds with a Value_Domain that describes a set of possible values that may be recorded in an instance of the Data_Element', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.DataElementConcept', verbose_name='Data Element Concept'),
        ),
        migrations.AlterField(
            model_name='dataelement',
            name='valueDomain',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='binds with a Data_Element_Concept that provides the meaning for the Data_Element', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ValueDomain', verbose_name='Value Domain'),
        ),
        migrations.AlterField(
            model_name='dataelementconcept',
            name='conceptualDomain',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='references a Conceptual_Domain that is part of the specification of the Data_Element_Concept', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ConceptualDomain', verbose_name='Conceptual Domain'),
        ),
        migrations.AlterField(
            model_name='dataelementconcept',
            name='objectClass',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='references an Object_Class that is part of the specification of the Data_Element_Concept', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ObjectClass', verbose_name='Object Class'),
        ),
        migrations.AlterField(
            model_name='dataelementconcept',
            name='property',
            field=aristotle_mdr.fields.ConceptForeignKey(blank=True, help_text='references a Property that is part of the specification of the Data_Element_Concept', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.Property', verbose_name='Property'),
        ),
        migrations.AlterField(
            model_name='discussioncomment',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='discussionpost',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='permissiblevalue',
            name='value_meaning',
            field=models.ForeignKey(blank=True, help_text='A reference to the value meaning that this designation relates to', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ValueMeaning'),
        ),
        migrations.AlterField(
            model_name='possumprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='recordrelation',
            name='organization_record',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='aristotle_mdr.OrganizationRecord'),
        ),
        migrations.AlterField(
            model_name='sandboxshare',
            name='profile',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='share', to='aristotle_mdr.PossumProfile'),
        ),
        migrations.AlterField(
            model_name='supersederelationship',
            name='review',
            field=aristotle_mdr.fields.ConceptForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supersedes', to='aristotle_mdr_review_requests.ReviewRequest'),
        ),
        migrations.AlterField(
            model_name='supplementaryvalue',
            name='value_meaning',
            field=models.ForeignKey(blank=True, help_text='A reference to the value meaning that this designation relates to', null=True, on_delete=django.db.models.deletion.SET_NULL, to='aristotle_mdr.ValueMeaning'),
        ),
    ]
