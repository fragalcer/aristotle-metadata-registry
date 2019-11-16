# Generated by Django 2.2.6 on 2019-11-12 05:46

import aristotle_mdr.fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aristotle_mdr', '0073_squashed_0075__v310_squishy_part2'),
    ]
    replaces = [
        ('aristotle_mdr_view_history', '0001_initial'),
        ('aristotle_mdr_view_history', '0002_auto_20190809_1233'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserViewHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('view_date', models.DateTimeField(default=django.utils.timezone.now, help_text='When the item was viewed')),
                ('concept', aristotle_mdr.fields.ConceptForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_view_history', to='aristotle_mdr._concept')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='recently_viewed_metadata', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
