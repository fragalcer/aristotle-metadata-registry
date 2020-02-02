from aristotle_mdr.tests.migration_test_utils import MigrationsTestCase
from django.test import TestCase
from unittest import skip


@skip("Old migration test. It will be squashed.")
class TestMoveImplementationDateMigration(MigrationsTestCase, TestCase):
    app = 'aristotle_dse'

    migrate_from = [
        ('aristotle_mdr', '0057_auto_20190329_1609'),
        ('aristotle_dse', '0021_auto_20190415_0012'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    migrate_to = [
        ('aristotle_dse', '0022_auto_20190501_1043')
    ]

    def setUpBeforeMigration(self, apps):
        # Below forces content types to be created for the migrated items
        from django.contrib.contenttypes.management import create_contenttypes
        app_config = apps.get_app_config('aristotle_dse')
        app_config.models_module = app_config.models_module or True
        create_contenttypes(app_config)

        app_config = apps.get_app_config('aristotle_dse')
        app_config.models_module = app_config.models_module or True
        create_contenttypes(app_config)

        DataSetSpecification = apps.get_model('aristotle_dse', 'DataSetSpecification')

        self.implementation_start_date = "2018-01-01"
        self.implementation_end_date = "2019-01-01"

        self.dss = DataSetSpecification.objects.create(
            name='My DSS',
            definition='test defn',
            implementation_start_date=self.implementation_start_date,
            implementation_end_date=self.implementation_end_date,
        )

    def test_migration(self):
        apps = self.apps
        # Below forces content types to be created for the migrated items
        from django.contrib.contenttypes.management import create_contenttypes
        app_config = apps.get_app_config('aristotle_dse')
        app_config.models_module = app_config.models_module or True
        create_contenttypes(app_config)

        DataSetSpecification = self.apps.get_model('aristotle_dse', 'DataSetSpecification')
        CustomField = self.apps.get_model('aristotle_mdr_custom_fields', 'CustomField')
        ContentType = self.apps.get_model('contenttypes', 'ContentType')
        CustomValue = self.apps.get_model('aristotle_mdr_custom_fields', 'CustomValue')

        ctype = ContentType.objects.get(
            app_label='aristotle_dse',
            model='datasetspecification',
        )

        self.dss = DataSetSpecification.objects.get(pk=self.dss.pk)

        isd_field = CustomField.objects.get(
            name="Implementation Start Date",
            allowed_model=ctype,
        )
        ied_field = CustomField.objects.get(
            name="Implementation End Date",
            allowed_model=ctype,
        )

        self.assertEqual('date', isd_field.type)
        self.assertEqual('date', ied_field.type)

        isd_value = CustomValue.objects.get(field=isd_field, concept=self.dss)
        ied_value = CustomValue.objects.get(field=ied_field, concept=self.dss)

        self.assertEqual(isd_value.content, self.implementation_start_date)
        self.assertEqual(ied_value.content, self.implementation_end_date)


class TestDSSGroupingLinkedGroupThroughTable(MigrationsTestCase, TestCase):
    app = 'aristotle_dse'
    migrate_from = [
        ('aristotle_mdr', '0085_remove_temp_field'),
        ('aristotle_dse', '0038_create_new_through_tables'),
    ]
    migrate_to = '0039_copy_paste_data_from_old_through_table_to_new'

    def setUpBeforeMigration(self, apps):
        DSSGrouping = apps.get_model('aristotle_dse', 'DSSGrouping')
        DataSetSpecification = apps.get_model('aristotle_dse', 'DataSetSpecification')

        self.my_dss = DataSetSpecification.objects.create(
            name="My DSS",
            definition="My definition",
        )
        self.my_dss_2 = DataSetSpecification.objects.create(
            name="My DSS 2",
            definition="My definition 2",
        )
        self.my_dss_3 = DataSetSpecification.objects.create(
            name="My DSS 3",
            definition="My definition 3",
        )
        self.my_dss_4 = DataSetSpecification.objects.create(
            name="My DSS 3",
            definition="My definition 3",
        )
        self.dss_grouping_1 = DSSGrouping.objects.create(
            name="DSSGroupingForTest",
            definition="DSSGroupingDefinition",
            dss=self.my_dss,
        )
        self.dss_grouping_2 = DSSGrouping.objects.create(
            name="DSSGroupingTwoForTest",
            definition="DSSGroupingDefinition 2",
            dss=self.my_dss_2,
        )
        self.dss_grouping_3 = DSSGrouping.objects.create(
            name="DSSGroupingThreeForTest",
            definition="DSSGroupingDefinition 3",
            dss=self.my_dss_2,
        )
        self.dss_grouping_4 = DSSGrouping.objects.create(
            name="DSSGroupingFourForTest",
            definition="DSSGroupingDefinition 3",
            dss=self.my_dss_2,
        )
        self.dss_grouping_2.linked_group.set([self.dss_grouping_1])
        self.dss_grouping_3.linked_group.set([self.dss_grouping_1])
        self.dss_grouping_4.linked_group.set([self.dss_grouping_3])

        # Make sure at this point the old through table is still there:
        self.assertEqual(self.dss_grouping_2.linked_group.through.__name__, 'DSSGrouping_linked_group')

        # Make sure the old through table has 3 DSSGrouping objects:
        self.assertEqual(self.dss_grouping_2.linked_group.through.objects.all().count(), 3)

    def test_data_actually_copy_pasted_from_old_through_table_to_new_through_table(self):
        DSSGroupingLinkedGroupThrough = self.dss_grouping_2.linked_group_new.through

        # Through table was actually created:
        self.assertEqual(DSSGroupingLinkedGroupThrough.__name__, 'DSSGroupingLinkedGroupThrough')

        # Make sure the new through table has 3 DSSGroupingLinkedGroupThrough objects:
        self.assertEqual(DSSGroupingLinkedGroupThrough.objects.all().count(), 3)
        # Make sure that this Foreign key 'to_dssgrouping' does have a reference to 'self' in 'from_fields':
        self.assertEqual(
            DSSGroupingLinkedGroupThrough.objects.first()._meta.get_field('to_dssgrouping').__dict__.get(
                'from_fields')[0],
            'self'
        )
        # Make sure that this Foreign key 'to_dssgrouping' does have a reference to 'uuid' in 'to_fields':
        self.assertEqual(
            DSSGroupingLinkedGroupThrough.objects.first()._meta.get_field('to_dssgrouping').__dict__.get(
                'to_fields')[0],
            'uuid'
        )
        # Make sure that this Foreign Keys in the new through table are referenced by uuids:
        self.assertEqual(DSSGroupingLinkedGroupThrough.objects.first().from_dssgrouping_id,
                         self.dss_grouping_2.uuid)
        self.assertEqual(DSSGroupingLinkedGroupThrough.objects.first().to_dssgrouping_id,
                         self.dss_grouping_1.uuid)


class TestDSSDEInclusionSpecialisationClassesThroughTable(MigrationsTestCase, TestCase):
    app = 'aristotle_dse'
    migrate_from = [
        ('aristotle_mdr', '0085_remove_temp_field'),
        ('aristotle_dse', '0038_create_new_through_tables'),
    ]
    migrate_to = '0039_copy_paste_data_from_old_through_table_to_new'

    def setUpBeforeMigration(self, apps):
        DataElement = apps.get_model('aristotle_mdr', 'dataelement')
        DataSetSpecification = apps.get_model('aristotle_dse', 'datasetspecification')
        DSSDEInclusion = apps.get_model('aristotle_dse', 'dssdeinclusion')
        ObjectClass = apps.get_model('aristotle_mdr', 'objectclass')

        self.de = DataElement.objects.create(name="Test DE")
        self.dss = DataSetSpecification.objects.create(name="Test DSS")
        self.dssdei = DSSDEInclusion.objects.create(
            data_element=self.de,
            dss=self.dss,
        )

        self.oc_1 = ObjectClass.objects.create(
            name="Test OC 1"
        )
        self.oc_2 = ObjectClass.objects.create(
            name="Test OC 2"
        )
        self.oc_3 = ObjectClass.objects.create(
            name="Test OC 3"
        )

        self.dssdei.specialisation_classes.add(
            self.oc_1,
            self.oc_2,
            self.oc_3,
        )

        # Make sure at this point the old through table is still there:
        self.assertEqual(self.dssdei.specialisation_classes.through.__name__, 'DSSDEInclusion_specialisation_classes')

        # Make sure the old through table has 3 ObjectClass objects:
        self.assertEqual(self.dssdei.specialisation_classes.through.objects.all().count(), 3)

    def test_data_actually_copy_pasted_from_old_through_table_to_new_through_table(self):
        DSSDEInclusionSpecialisationClassesThrough = self.dssdei.specialisation_classes_new.through

        # Through table was actually created:
        self.assertEqual(DSSDEInclusionSpecialisationClassesThrough.__name__,
                         'DSSDEInclusionSpecialisationClassesThrough')

        # Make sure the new through table has 3 DSSDEInclusionSpecialisationClassesThrough objects:
        self.assertEqual(DSSDEInclusionSpecialisationClassesThrough.objects.all().count(), 3)

        # Make sure that this Foreign key 'dssdeinclusion' does have a reference to 'self' in 'from_fields':
        self.assertEqual(
            DSSDEInclusionSpecialisationClassesThrough.objects.first()._meta.get_field('dssdeinclusion').__dict__.get(
                'from_fields')[0],
            'self'
        )
        # Make sure that this Foreign key 'dssdeinclusion' does have a reference to 'uuid' in 'to_fields':
        self.assertEqual(
            DSSDEInclusionSpecialisationClassesThrough.objects.first()._meta.get_field('dssdeinclusion').__dict__.get(
                'to_fields')[0],
            'uuid'
        )
        # Make sure that this Foreign Keys in the new through table are referenced by uuids:
        self.assertEqual(DSSDEInclusionSpecialisationClassesThrough.objects.first().dssdeinclusion_id, self.dssdei.uuid)

        # Make sure there is actually a connection in the through table:
        through_object_1 = DSSDEInclusionSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 1")
        through_object_2 = DSSDEInclusionSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 2")
        through_object_3 = DSSDEInclusionSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 3")
        self.assertEqual(through_object_1.objectclass_id, self.oc_1.id)
        self.assertEqual(through_object_2.objectclass_id, self.oc_2.id)
        self.assertEqual(through_object_3.objectclass_id, self.oc_3.id)


class TestDistributionDataElementPathSpecialisationClassesThroughTable(MigrationsTestCase, TestCase):
    app = 'aristotle_dse'
    migrate_from = [
        ('aristotle_mdr', '0085_remove_temp_field'),
        ('aristotle_dse', '0038_create_new_through_tables'),
    ]
    migrate_to = '0039_copy_paste_data_from_old_through_table_to_new'

    def setUpBeforeMigration(self, apps):
        DataElement = apps.get_model('aristotle_mdr', 'dataelement')
        DataSetSpecification = apps.get_model('aristotle_dse', 'datasetspecification')
        DistributionDataElementPath = apps.get_model('aristotle_dse', 'distributiondataelementpath')
        ObjectClass = apps.get_model('aristotle_mdr', 'objectclass')

        self.de = DataElement.objects.create(name="Test DE")
        self.dss = DataSetSpecification.objects.create(name="Test DSS")
        self.ddep = DistributionDataElementPath.objects.create(
            data_element=self.de,
        )

        self.oc_1 = ObjectClass.objects.create(
            name="Test OC 1"
        )
        self.oc_2 = ObjectClass.objects.create(
            name="Test OC 2"
        )
        self.oc_3 = ObjectClass.objects.create(
            name="Test OC 3"
        )

        self.ddep.specialisation_classes.add(
            self.oc_1,
            self.oc_2,
            self.oc_3,
        )

        # Make sure at this point the old through table is still there:
        self.assertEqual(self.ddep.specialisation_classes.through.__name__,
                         'DistributionDataElementPath_specialisation_classes')

        # Make sure the old through table has 3 ObjectClass objects:
        self.assertEqual(self.ddep.specialisation_classes.through.objects.all().count(), 3)

    def test_data_actually_copy_pasted_from_old_through_table_to_new_through_table(self):
        DistributionDataElementPathSpecialisationClassesThrough = self.ddep.specialisation_classes_new.through

        # Through table was actually created:
        self.assertEqual(DistributionDataElementPathSpecialisationClassesThrough.__name__,
                         'DistributionDataElementPathSpecialisationClassesThrough')

        # Make sure the new through table has 3 DistributionDataElementPathSpecialisationClassesThrough objects:
        self.assertEqual(DistributionDataElementPathSpecialisationClassesThrough.objects.all().count(), 3)

        # Make sure that this Foreign key 'distributiondataelementpath' does have a reference to 'self' in 'from_fields':
        self.assertEqual(
            DistributionDataElementPathSpecialisationClassesThrough.objects.first()._meta.get_field(
                'distributiondataelementpath').__dict__.get(
                'from_fields')[0],
            'self'
        )
        # Make sure that this Foreign key 'distributiondataelementpath' does have a reference to 'uuid' in 'to_fields':
        self.assertEqual(
            DistributionDataElementPathSpecialisationClassesThrough.objects.first()._meta.get_field(
                'distributiondataelementpath').__dict__.get(
                'to_fields')[0],
            'uuid'
        )
        # Make sure that this Foreign Keys in the new through table are referenced by uuids:
        self.assertEqual(
            DistributionDataElementPathSpecialisationClassesThrough.objects.first().distributiondataelementpath_id,
            self.ddep.uuid)

        # Make sure there is actually a connection in the through table:
        through_object_1 = DistributionDataElementPathSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 1")
        through_object_2 = DistributionDataElementPathSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 2")
        through_object_3 = DistributionDataElementPathSpecialisationClassesThrough.objects.get(objectclass__name="Test OC 3")
        self.assertEqual(through_object_1.objectclass_id, self.oc_1.id)
        self.assertEqual(through_object_2.objectclass_id, self.oc_2.id)
        self.assertEqual(through_object_3.objectclass_id, self.oc_3.id)


class UUIDToPrimaryKeyTestBaseForDSSDEInclusionsAndDSSGroupings(MigrationsTestCase, TestCase):

    def setUpBeforeMigration(self, apps):
        self.DataElement = apps.get_model('aristotle_mdr', 'dataelement')
        self.DataSetSpecification = apps.get_model('aristotle_dse', 'datasetspecification')
        self.DSSGroupingLinkedGroupThrough = apps.get_model('aristotle_dse', 'dssgroupinglinkedgroupthrough')
        self.DSSGrouping = apps.get_model('aristotle_dse', 'dssgrouping')
        self.DSSDEInclusion = apps.get_model('aristotle_dse', 'dssdeinclusion')
        self.de = self.DataElement.objects.create(
            name="Test DE"
        )
        self.dss = self.DataSetSpecification.objects.create(
            name="Test DSS",
        )
        self.dssgrouping_1 = self.DSSGrouping.objects.create(
            name="Test DSSGrouping 1",
            dss=self.dss
        )
        self.dssgrouping_2 = self.DSSGrouping.objects.create(
            name="Test DSSGrouping 2",
            dss=self.dss
        )


class TestDSSDEInclusionAndDSSGroupingLinkedGroupThroughPrimaryKeyChange(
    UUIDToPrimaryKeyTestBaseForDSSDEInclusionsAndDSSGroupings):
    migrate_from = '0043_add_temp_field'
    migrate_to = '0044_copy_and_paste_foreign_value'

    def setUpBeforeMigration(self, apps):

        super().setUpBeforeMigration(apps)

        # Make sure the temporary fields are UUID fields:
        self.assertEqual(self.DSSDEInclusion._meta.get_field('group_temp').get_internal_type(), 'UUIDField')
        self.assertEqual(
            self.DSSGroupingLinkedGroupThrough._meta.get_field('from_dssgrouping_temp').get_internal_type(),
            'UUIDField')
        self.assertEqual(self.DSSGroupingLinkedGroupThrough._meta.get_field('to_dssgrouping_temp').get_internal_type(),
                         'UUIDField')

        self.DSSGroupingLinkedGroupThrough.objects.create(
            from_dssgrouping=self.dssgrouping_1,
            to_dssgrouping=self.dssgrouping_2
        )
        self.DSSDEInclusion.objects.create(
            data_element=self.de,
            dss=self.dss,
            group=self.dssgrouping_1
        )
        # Make sure the objects have objects assigned to them:
        dssglgt = self.DSSGroupingLinkedGroupThrough.objects.last()
        dssdei = self.DSSDEInclusion.objects.last()
        self.assertEqual(dssglgt.from_dssgrouping, self.dssgrouping_1)
        self.assertEqual(dssglgt.to_dssgrouping, self.dssgrouping_2)
        self.assertEqual(dssdei.group, self.dssgrouping_1)

    def test_migration(self):

        DSSDEInclusion = self.apps.get_model('aristotle_dse', 'dssdeinclusion')
        DSSGroupingLinkedGroupThrough = self.apps.get_model('aristotle_dse', 'dssgroupinglinkedgroupthrough')
        DSSGrouping = self.apps.get_model('aristotle_dse', 'dssgrouping')
        dssdei = DSSDEInclusion.objects.last()
        dssg1 = DSSGrouping.objects.get(name="Test DSSGrouping 1")
        dssg2 = DSSGrouping.objects.get(name="Test DSSGrouping 2")
        dssglgt = DSSGroupingLinkedGroupThrough.objects.last()

        # Make sure the temporary uuid fields have the value of the foreign key field:
        self.assertEqual(dssdei.group_temp, dssg1.uuid)
        self.assertEqual(dssglgt.from_dssgrouping_temp, dssg1.uuid)
        self.assertEqual(dssglgt.to_dssgrouping_temp, dssg2.uuid)


class TestDSSGroupingUUIDForeignKey(UUIDToPrimaryKeyTestBaseForDSSDEInclusionsAndDSSGroupings):
    migrate_from = '0046_add_foreign_key_field'
    migrate_to = '0047_copy_and_paste_to_foreign_key'

    def setUpBeforeMigration(self, apps):
        super().setUpBeforeMigration(apps)

        # Make sure the new Field is a Foreign Key field:
        self.assertEqual(self.DSSDEInclusion._meta.get_field('group').get_internal_type(), 'ForeignKey')
        self.assertEqual(self.DSSGroupingLinkedGroupThrough._meta.get_field('from_dssgrouping').get_internal_type(),
                         'ForeignKey')
        self.assertEqual(self.DSSGroupingLinkedGroupThrough._meta.get_field('to_dssgrouping').get_internal_type(),
                         'ForeignKey')

        self.DSSGroupingLinkedGroupThrough.objects.create(
            from_dssgrouping_temp=self.dssgrouping_1.uuid,
            to_dssgrouping_temp=self.dssgrouping_2.uuid
        )
        self.DSSDEInclusion.objects.create(
            data_element=self.de,
            dss=self.dss,
            group_temp=self.dssgrouping_1.uuid
        )

    def test_migration(self):
        DSSDEInclusion = self.apps.get_model('aristotle_dse', 'dssdeinclusion')
        DSSGroupingLinkedGroupThrough = self.apps.get_model('aristotle_dse', 'dssgroupinglinkedgroupthrough')
        DSSGrouping = self.apps.get_model('aristotle_dse', 'dssgrouping')
        dssdei = DSSDEInclusion.objects.last()
        dssg1 = DSSGrouping.objects.get(name="Test DSSGrouping 1")
        dssg2 = DSSGrouping.objects.get(name="Test DSSGrouping 2")
        dssglgt = DSSGroupingLinkedGroupThrough.objects.last()
        self.assertEqual(dssglgt.from_dssgrouping, dssg1)  # Check that new foreign key is working.
        self.assertEqual(dssglgt.to_dssgrouping, dssg2)  # Check that new foreign key is working.
        self.assertEqual(dssdei.group, dssg1)  # Check that new foreign key is working.

        # The new fields are foreign key (relation) fields:
        self.assertTrue(DSSGroupingLinkedGroupThrough._meta.get_field('from_dssgrouping').is_relation)
        self.assertTrue(DSSGroupingLinkedGroupThrough._meta.get_field('to_dssgrouping').is_relation)
        self.assertTrue(DSSDEInclusion._meta.get_field('group').is_relation)

        self.assertEqual(dssglgt.from_dssgrouping.uuid, dssg1.uuid)
        self.assertEqual(dssglgt.to_dssgrouping.uuid, dssg2.uuid)
