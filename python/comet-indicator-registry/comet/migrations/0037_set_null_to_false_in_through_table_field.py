# Generated by Django 2.2.7 on 2020-01-29 23:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0036_auto_20191024_0100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='indicatorframeworkdimensionsthrough',
            name='frameworkdimension',
            field=models.ForeignKey(
                blank=True,
                to='comet.FrameworkDimension',
                on_delete=django.db.models.deletion.CASCADE, )
        ),
    ]