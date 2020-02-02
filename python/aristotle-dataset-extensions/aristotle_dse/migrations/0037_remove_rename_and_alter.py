from django.db import migrations, models
import django.db.models.deletion
from aristotle_mdr.utils.migration_utils import data_copy_and_paste


def duplicate_model_foreign_key(apps, schema_editor):
    dssdeinclusion_model = apps.get_model('aristotle_dse', 'dssdeinclusion')
    data_copy_and_paste(dssdeinclusion_model, 'group', 'group_new')


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0036_copy_and_paste_dssdeinclusion_group'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dssdeinclusion',
            name='group',
        ),
        migrations.RenameField(
            model_name='dssdeinclusion',
            old_name='group_new',
            new_name='group',
        ),
        migrations.AlterField(
            model_name='dssdeinclusion',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    to='aristotle_dse.DSSGrouping', to_field='uuid'),
        ),
    ]
