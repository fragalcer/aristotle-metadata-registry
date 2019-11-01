# Generated by Django 2.2.4 on 2019-10-16 10:03

import aristotle_mdr.contrib.reviews.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('aristotle_mdr', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    replaces = [
        ('aristotle_mdr_review_requests', '0001_initial'),
        ('aristotle_mdr_review_requests', '0002_auto_20181031_0047'),
        ('aristotle_mdr_review_requests', '0003_auto_20181126_1707'),
        ('aristotle_mdr_review_requests', '0004_auto_20181205_1925'),
        ('aristotle_mdr_review_requests', '0005_auto_20190809_1233'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('title', models.TextField(blank=True, help_text='An optional message accompanying a request, this will accompany the approved registration status', null=True)),
                ('status', models.IntegerField(choices=[(0, 'Open'), (5, 'Revoked'), (10, 'Approved'), (15, 'Closed')], default=0, help_text='Status of a review')),
                ('target_registration_state', models.IntegerField(blank=True, choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], help_text='The state at which a user wishes a metadata item to be endorsed', null=True)),
                ('registration_date', models.DateField(blank=True, help_text='date and time you want the metadata to be registered from', null=True, verbose_name='Date registration effective')),
                ('due_date', models.DateField(blank=True, help_text='Date and time a response is required', null=True, verbose_name='Date response required')),
                ('cascade_registration', models.IntegerField(choices=[(0, 'No'), (1, 'Yes')], default=0, help_text='Update the registration of associated items')),
                ('concepts', models.ManyToManyField(related_name='rr_review_requests', to='aristotle_mdr._concept')),
                ('registration_authority', models.ForeignKey(help_text='The registration authority the requester wishes to endorse the metadata item', on_delete=django.db.models.deletion.CASCADE, related_name='rr_requested_reviews', to='aristotle_mdr.RegistrationAuthority')),
                ('requester', models.ForeignKey(help_text='The user requesting a review', on_delete=django.db.models.deletion.PROTECT, related_name='rr_requested_reviews', to=settings.AUTH_USER_MODEL)),
                ('workgroup', models.ForeignKey(help_text='A workgroup associated with this review', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rr_workgroup_reviews', to='aristotle_mdr.Workgroup')),
            ],
            options={
                'abstract': False,
            },
            bases=(aristotle_mdr.contrib.reviews.models.StatusMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ReviewStatusChangeTimeline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('status', models.IntegerField(choices=[(0, 'Open'), (5, 'Revoked'), (10, 'Approved'), (15, 'Closed')], default=0, help_text='Status of a review')),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='state_changes', to='aristotle_mdr_review_requests.ReviewRequest')),
            ],
            options={
                'ordering': ['created'],
            },
            bases=(aristotle_mdr.contrib.reviews.models.StatusMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ReviewEndorsementTimeline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('registration_state', models.IntegerField(choices=[(0, 'Not Progressed'), (1, 'Incomplete'), (2, 'Candidate'), (3, 'Recorded'), (4, 'Qualified'), (5, 'Standard'), (6, 'Preferred Standard'), (7, 'Superseded'), (8, 'Retired')], help_text='The state at which a user wishes a metadata item to be endorsed')),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='endorsements', to='aristotle_mdr_review_requests.ReviewRequest')),
            ],
            options={
                'ordering': ['created'],
            },
        ),
        migrations.CreateModel(
            name='ReviewComment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('body', models.TextField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='aristotle_mdr_review_requests.ReviewRequest')),
            ],
            options={
                'ordering': ['created'],
            },
        ),
    ]
