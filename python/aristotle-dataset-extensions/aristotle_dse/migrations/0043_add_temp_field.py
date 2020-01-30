# Generated by Django 2.2.5 on 2019-10-17 23:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0042_change_pk_to_uuid_for_non_referenced_dse_models'),
        ('aristotle_mdr', '0086_auto_20191024_0100')
    ]

    operations = [
        migrations.AddField(
            model_name='dssgroupinglinkedgroupthrough',
            name='from_dssgrouping_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dssgroupinglinkedgroupthrough',
            name='to_dssgrouping_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dssdeinclusion',
            name='group_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dssdeinclusionspecialisationclassesthrough',
            name='dssdeinclusion_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='distributiondataelementpathspecialisationclassesthrough',
            name='distributiondataelementpath_temp',
            field=models.UUIDField(blank=True, null=True),
        ),
    ]