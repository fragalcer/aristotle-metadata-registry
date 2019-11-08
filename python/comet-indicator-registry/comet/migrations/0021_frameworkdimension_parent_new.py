# Generated by Django 2.2.5 on 2019-09-30 04:43

from django.db import migrations
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0020_auto_20190918_1612'),
        ('aristotle_mdr', '0078_auto_20190918_1610'),
    ]

    operations = [
        migrations.AddField(
            model_name='frameworkdimension',
            name='parent_new',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='comet.FrameworkDimension', to_field='uuid'),
        ),
    ]