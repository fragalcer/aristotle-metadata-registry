from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('comet', '0027_auto_20191003_0123'),
    ]

    operations = [
        migrations.RenameField(
            model_name='indicator',
            old_name='dimensions_new',
            new_name='dimensions',
        ),
    ]
