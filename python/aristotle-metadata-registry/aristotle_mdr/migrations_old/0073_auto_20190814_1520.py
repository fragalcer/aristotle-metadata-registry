# Generated by Django 2.2 on 2019-08-14 05:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0072_auto_20190809_1502'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='permissiblevalue',
            options={'ordering': ['order'], 'verbose_name': 'Permissible Value'},
        ),
        migrations.AlterModelOptions(
            name='supplementaryvalue',
            options={'ordering': ['order'], 'verbose_name': 'Supplementary Value'},
        ),
        migrations.AddIndex(
            model_name='_concept',
            index=models.Index(fields=['uuid'], name='aristotle_m_uuid_6cec97_idx'),
        ),
    ]