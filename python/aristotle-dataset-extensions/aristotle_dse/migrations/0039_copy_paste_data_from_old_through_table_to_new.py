from django.db import migrations
from aristotle_mdr.utils.migration_utils import data_copy_and_paste_from_m2m_through_model


def copy_and_paste_data_from_old_through_table_to_new(apps, schema_editor):

    DSSGrouping = apps.get_model('aristotle_dse', 'dssgrouping')
    DSSGroupingLinkedGroupThrough = apps.get_model('aristotle_dse', 'dssgroupinglinkedgroupthrough')
    data_copy_and_paste_from_m2m_through_model(DSSGrouping, DSSGroupingLinkedGroupThrough, 'linked_group', with_self=True)

    DSSDEInclusion = apps.get_model('aristotle_dse', 'dssdeinclusion')
    DSSDEInclusionSpecialisationClassesThrough = apps.get_model('aristotle_dse', 'dssdeinclusionspecialisationclassesthrough')
    data_copy_and_paste_from_m2m_through_model(DSSDEInclusion, DSSDEInclusionSpecialisationClassesThrough, 'specialisation_classes')

    DistributionDataElementPath = apps.get_model('aristotle_dse', 'distributiondataelementpath')
    DistributionDataElementPathSpecialisationClassesThrough = apps.get_model('aristotle_dse',
                                                                             'distributiondataelementpathspecialisationclassesthrough')
    data_copy_and_paste_from_m2m_through_model(DistributionDataElementPath,
                                               DistributionDataElementPathSpecialisationClassesThrough,
                                               'specialisation_classes')


def copy_and_paste_data_from_new_through_table_to_old(apps, schema_editor):

    DSSGrouping = apps.get_model('aristotle_dse', 'dssgrouping')
    DSSGrouping_Linked_Group = apps.get_model('aristotle_dse', 'dssgrouping_linked_group')
    data_copy_and_paste_from_m2m_through_model(DSSGrouping, DSSGrouping_Linked_Group, 'linked_group_new', with_self=True)

    DSSDEInclusion = apps.get_model('aristotle_dse', 'dssdeinclusion')
    DSSDEInclusion_Specialisation_Classes = apps.get_model('aristotle_dse', 'dssdeinclusion_specialisation_classes')
    data_copy_and_paste_from_m2m_through_model(DSSDEInclusion, DSSDEInclusion_Specialisation_Classes, 'specialisation_classes_new')

    DistributionDataElementPath = apps.get_model('aristotle_dse', 'distributiondataelementpath')
    DistributionDataElementPathSpecialisationClassesThrough = DistributionDataElementPath.specialisation_classes.through
    data_copy_and_paste_from_m2m_through_model(DistributionDataElementPath,
                                               DistributionDataElementPathSpecialisationClassesThrough,
                                               'specialisation_classes_new')


class Migration(migrations.Migration):

    dependencies = [
        ('aristotle_dse', '0038_create_new_through_tables'),
    ]

    operations = [
        migrations.RunPython(copy_and_paste_data_from_old_through_table_to_new, reverse_code=copy_and_paste_data_from_new_through_table_to_old),
    ]
