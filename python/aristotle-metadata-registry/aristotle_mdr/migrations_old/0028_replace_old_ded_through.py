from django.db import migrations
import aristotle_mdr.fields

class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_mdr', '0027_add_ded_through_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dataelementderivation',
            name='derives',
        ),
        migrations.RemoveField(
            model_name='dataelementderivation',
            name='inputs',
        ),
        migrations.AddField(
            model_name='dataelementderivation',
            name='derives',
            field=aristotle_mdr.fields.ConceptManyToManyField(blank=True, help_text='binds with one or more output Data_Elements that are the result of the application of the Data_Element_Derivation.', null=True, related_name='derived_from', through='aristotle_mdr.DedDerivesThrough', to='aristotle_mdr.DataElement'),
        ),
        migrations.AddField(
            model_name='dataelementderivation',
            name='inputs',
            field=aristotle_mdr.fields.ConceptManyToManyField(blank=True, help_text='binds one or more input Data_Element(s) with a Data_Element_Derivation.', related_name='input_to_derivation', through='aristotle_mdr.DedInputsThrough', to='aristotle_mdr.DataElement'),
        ),
    ]
