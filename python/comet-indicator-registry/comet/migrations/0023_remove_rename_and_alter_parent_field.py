from django.db import migrations, models
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('comet', '0022_copy_and_paste_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='frameworkdimension',
            name='parent',
        ),
        migrations.RenameField(
            model_name='frameworkdimension',
            old_name='parent_new',
            new_name='parent',
        ),
        migrations.AlterField(
            model_name='frameworkdimension',
            name='parent',
            field=mptt.fields.TreeForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='comet.FrameworkDimension', to_field='uuid', related_name='child_dimensions'),
        ),
    ]
