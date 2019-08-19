# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0018_improve_request_reviews'),
    ]

    operations = [
        migrations.CreateModel(
            name='Link',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LinkEnd',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Relation',
            fields=[
                ('_concept_ptr', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept', auto_created=True, parent_link=True, primary_key=True, serialize=False)),
                ('arity', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(2)], help_text='number of elements in the relation')),
            ],
            options={
                'abstract': False,
            },
            bases=('aristotle_mdr._concept',),
        ),
        migrations.CreateModel(
            name='RelationRole',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('name', models.TextField(help_text='The primary name used for human identification purposes.')),
                ('definition', models.TextField(verbose_name='definition', help_text='Representation of a concept by a descriptive statement which serves to differentiate it from related concepts. (3.2.39)')),
                ('multiplicity', models.PositiveIntegerField(help_text='number of links which must (logically) be members of the source relation of this role, differing only by an end with this role as an end_role.')),
                ('ordinal', models.PositiveIntegerField(help_text='order of the relation role among other relation roles in the relation.')),
                ('relation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_links.Relation')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='linkend',
            name='concept',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr._concept'),
        ),
        migrations.AddField(
            model_name='linkend',
            name='link',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_links.Link'),
        ),
        migrations.AddField(
            model_name='linkend',
            name='role',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_links.RelationRole'),
        ),
        migrations.AddField(
            model_name='link',
            name='relation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='aristotle_mdr_links.Relation'),
        ),
    ]
