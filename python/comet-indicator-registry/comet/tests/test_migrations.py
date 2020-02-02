from aristotle_mdr.tests.migration_test_utils import MigrationsTestCase
from django.test import TestCase
from unittest import skip


@skip("Old migration test. It will be squashed.")
class TestSixToEightMigration(MigrationsTestCase, TestCase):
    app = 'comet'
    migrate_from = [
        ('aristotle_mdr', '0045__concept_superseded_by_items'),
        ('comet', '0005_auto_20181107_0433'),
    ]
    migrate_to = '0008_auto_20190218_0404'

    def setUpBeforeMigration(self, apps):
        Indicator = apps.get_model('comet', 'Indicator')
        IndicatorSet = apps.get_model('comet', 'IndicatorSet')
        IndicatorType = apps.get_model('comet', 'IndicatorType')
        IndicatorSetType = apps.get_model('comet', 'IndicatorSetType')
        de = apps.get_model('aristotle_mdr', 'DataElement')

        self.indicatorsettype = IndicatorSetType.objects.create(
            name='Indicator Set Type 1',
            definition='test defn',
        )

        self.indicatorset = IndicatorSet.objects.create(
            name='Indicator Set 1',
            definition='test defn',
            indicatorSetType=self.indicatorsettype
        )

        self.indicatortype = IndicatorType.objects.create(
            name='Indicator Type 1',
            definition='test defn',
        )

        self.indicator = Indicator.objects.create(
            name='Indicator 1',
            definition='test defn',
            indicatorType=self.indicatortype
        )

        self.de1 = de.objects.create(
            name='DE1',
            definition='test defn',
        )

        self.de2 = de.objects.create(
            name='DE2',
            definition='test defn',
        )

        self.de3 = de.objects.create(
            name='DE3',
            definition='test defn',
        )

        self.indicatorset.indicators.add(self.indicator)

        self.indicator.numerators.add(self.de1)
        self.indicator.denominators.add(self.de2)
        self.indicator.disaggregators.add(self.de3)

    def test_migration(self):
        Indicator = self.apps.get_model('comet', 'Indicator')

        numerator_model = self.apps.get_model('comet', 'IndicatorNumeratorDefinition')
        denominator_model = self.apps.get_model('comet', 'IndicatorDenominatorDefinition')
        disaggregation_model = self.apps.get_model('comet', 'IndicatorDisaggregationDefinition')

        indicator_obj = Indicator.objects.get(pk=self.indicator.pk)
        numerators_list = numerator_model.objects.filter(indicator=indicator_obj)
        denominators_list = denominator_model.objects.filter(indicator=indicator_obj)
        disaggregators_list = disaggregation_model.objects.filter(indicator=indicator_obj)

        self.assertEqual(1, numerators_list.count())
        self.assertEqual(self.de1.id, numerators_list.first().data_element_id)

        self.assertEqual(1, denominators_list.count())
        self.assertEqual(self.de2.id, denominators_list.first().data_element_id)

        self.assertEqual(1, disaggregators_list.count())
        self.assertEqual(self.de3.id, disaggregators_list.first().data_element_id)

        # Do indicator sets now
        IndicatorSet = self.apps.get_model('comet', 'IndicatorSet')
        inclusion_model = self.apps.get_model('comet', 'IndicatorInclusion')

        indicatorset_obj = IndicatorSet.objects.get(pk=self.indicatorset.pk)

        indicators_list = inclusion_model.objects.filter(indicator_set=indicatorset_obj)

        self.assertEqual(1, indicators_list.count())
        self.assertEqual(self.indicator.id, indicators_list.first().indicator_id)

        # Do indicator types now
        IndicatorType = self.apps.get_model('comet', 'IndicatorType')
        ind_type = IndicatorType.objects.get(pk=self.indicatortype.pk)

        self.assertEqual(indicator_obj.indicator_type_id, ind_type.pk)

        # Do indicator set types now
        IndicatorSetType = self.apps.get_model('comet', 'IndicatorSetType')
        ind_set_type = IndicatorSetType.objects.get(pk=self.indicatorsettype.pk)

        self.assertEqual(indicatorset_obj.indicator_set_type_id, ind_set_type.pk)


class ThroughtTableTestCaseBase(MigrationsTestCase, TestCase):

    def setUpBeforeMigration(self, apps):
        Framework = apps.get_model('comet', 'Framework')
        FrameworkDimension = apps.get_model('comet', 'FrameworkDimension')
        Indicator = apps.get_model('comet', 'Indicator')

        self.f = Framework.objects.create(
            name="Test F",
        )

        self.fd_1 = FrameworkDimension.objects.create(
            name="Test FD 1",
            framework=self.f,
            lft=1,
            rght=2,
            tree_id=3,
            level=4,
        )

        self.fd_2 = FrameworkDimension.objects.create(
            name="Test FD 2",
            framework=self.f,
            lft=1,
            rght=2,
            tree_id=3,
            level=4,
        )

        self.i = Indicator.objects.create(
            name="Test Indicator",
        )
        self.i.dimensions.set(
            [self.fd_1, self.fd_2]  # Assign two FrameworkDimension objects to our Indicator.
        )

        # Make sure at this point the old through table is still there:
        self.assertEqual(self.i.dimensions.through.__name__, 'Indicator_dimensions')
        # Make sure the old through table has 2 FrameworkDimension objects:
        self.assertEqual(self.i.dimensions.through.objects.all().count(), 2)


class TestIndicatorFrameworkDimensionsThroughAndUUIDForeignKeyLink(ThroughtTableTestCaseBase):
    # At this point, the data is in the old through table:
    migrate_from = '0024_create_indicator_dimension_through'
    # We need to check that the data has been transferred to the new through table and foreign key used the uuid field:
    migrate_to = '0025_copy_and_paste_data_through'

    def test_data_was_migrated_to_the_new_through_table_IndicatorFrameworkDimensionsThrough(self):

        IndicatorFrameworkDimensionsThrough = self.i.dimensions_new.through

        # Through table was actually created:
        self.assertEqual(IndicatorFrameworkDimensionsThrough.__name__, 'IndicatorFrameworkDimensionsThrough')
        # Make sure the new through table has 2 FrameworkDimension objects:
        self.assertEqual(IndicatorFrameworkDimensionsThrough.objects.all().count(), 2)
        # Make sure that this Foreign key is actually using uuid:
        self.assertEqual(
            IndicatorFrameworkDimensionsThrough.objects.first()._meta.get_field('frameworkdimension').__dict__.get(
                'to_fields')[0],
            'uuid'
        )
        # Make sure that this Foreign Key is referenced by UUID field (Foreign Key 'to_field' is actually working):
        self.assertEqual(IndicatorFrameworkDimensionsThrough.objects.first().frameworkdimension_id, self.fd_1.uuid)

        # Make sure that the link between Framework and Framework Dimension still exists:
        self.assertEqual(self.i.dimensions.first().framework.name, self.f.name)
        self.assertEqual(self.i.dimensions.all().count(), 2)


class TestIndicatorFrameworkDimensionsThroughAndUUIDForeignKeyLinkReverse(ThroughtTableTestCaseBase):
    # At this point, the data is in the new through table:
    migrate_from = '0025_copy_and_paste_data_through'
    # We need to check that the data has been transferred back to the old through table and foreign key used id.
    migrate_to = '0024_create_indicator_dimension_through'

    def test_data_was_migrated_to_the_old_through_table_IndicatorFrameworkDimensionsThrough(self):

        indicator_dimensions_through_model = self.i.dimensions.through

        # Through table was actually created:
        self.assertEqual(indicator_dimensions_through_model.__name__, 'Indicator_dimensions')
        # Make sure the old through table has 2 FrameworkDimension objects:
        self.assertEqual(indicator_dimensions_through_model.objects.all().count(), 2)
        # Make sure that this Foreign key does not have a to_fields attribute:
        self.assertEqual(
            indicator_dimensions_through_model.objects.first()._meta.get_field('frameworkdimension').__dict__.get(
                'to_fields')[0],
            None
        )
        # Make sure that this Foreign Key is referenced by the id field (Because 'to_field' is nos assigned):
        self.assertEqual(indicator_dimensions_through_model.objects.first().frameworkdimension_id, self.fd_1.id)


class UUIDToPrimaryKeyTestBaseForFrameworkDimensions(MigrationsTestCase, TestCase):

    def setUpBeforeMigration(self, apps):
        self.Indicator = apps.get_model('comet', 'indicator')
        self.Framework = apps.get_model('comet', 'framework')
        self.FrameworkDimension = apps.get_model('comet', 'frameworkdimension')
        self.IndicatorFrameworkDimensionsThrough = apps.get_model('comet', 'indicatorframeworkdimensionsthrough')
        self.i = self.Indicator.objects.create(
            name='Test indicator',
            definition='Test defn',

        )
        self.f = self.Framework.objects.create(
            name="Test Framework"
        )
        self.fd_parent = self.FrameworkDimension.objects.create(
            name="Test FrameworkDimension Parent",
            framework=self.f,
            lft=1,
            rght=2,
            tree_id=3,
            level=4,
        )


class TestFrameworkDimensionAndIndicatorFrameworkDimensionsThroughPrimaryKeyChange(UUIDToPrimaryKeyTestBaseForFrameworkDimensions):

    migrate_from = '0030_add_temp_field'
    migrate_to = '0031_copy_and_paste_foreign_value'

    def setUpBeforeMigration(self, apps):
        super().setUpBeforeMigration(apps)

        # Make sure the temporary fields are UUID fields:
        self.assertEqual(self.FrameworkDimension._meta.get_field('parent_temp').get_internal_type(), 'UUIDField')
        self.assertEqual(self.IndicatorFrameworkDimensionsThrough._meta.get_field('frameworkdimension_temp').get_internal_type(), 'UUIDField')

        self.fd = self.FrameworkDimension.objects.create(
            name="Test FrameworkDimension",
            framework=self.f,
            lft=1,
            rght=2,
            tree_id=3,
            level=4,
            parent=self.fd_parent,
        )
        self.ifdt = self.IndicatorFrameworkDimensionsThrough.objects.create(
            frameworkdimension=self.fd,
            indicator=self.i,
        )
        # Make sure the objects have objects assigned to them:
        ifdt = self.IndicatorFrameworkDimensionsThrough.objects.last()
        fd = self.FrameworkDimension.objects.last()
        self.assertEqual(ifdt.frameworkdimension, self.fd)
        self.assertEqual(fd.parent, self.fd_parent)

    def test_migration(self):
        FrameworkDimension = self.apps.get_model('comet', 'frameworkdimension')
        IndicatorFrameworkDimensionsThrough = self.apps.get_model('comet', 'indicatorframeworkdimensionsthrough')

        fd = FrameworkDimension.objects.last()
        fd_parent = FrameworkDimension.objects.get(name="Test FrameworkDimension Parent")
        ifdt = IndicatorFrameworkDimensionsThrough.objects.last()

        # Make sure the temporary uuid fields have the value of the foreign key field:
        self.assertEqual(fd.parent_temp, fd_parent.uuid)
        self.assertEqual(ifdt.frameworkdimension_temp, fd.uuid)


class TestRelationRoleUUIDForeignKey(UUIDToPrimaryKeyTestBaseForFrameworkDimensions):

    migrate_from = '0033_add_foreign_key_field'
    migrate_to = '0034_copy_and_paste_to_foreign_key'

    def setUpBeforeMigration(self, apps):
        super().setUpBeforeMigration(apps)

        # Make sure the new Field is a Foreign Key field:
        self.assertEqual(self.FrameworkDimension._meta.get_field('parent').get_internal_type(), 'TreeForeignKey')
        self.assertEqual(self.IndicatorFrameworkDimensionsThrough._meta.get_field('frameworkdimension').get_internal_type(), 'ForeignKey')

        self.fd = self.FrameworkDimension.objects.create(
            name="Test FrameworkDimension",
            framework=self.f,
            lft=1,
            rght=2,
            tree_id=3,
            level=4,
            parent_temp=self.fd_parent.uuid,
        )

        self.ifdt = self.IndicatorFrameworkDimensionsThrough.objects.create(
            frameworkdimension_temp=self.fd.uuid,
            indicator=self.i,
        )

    def test_migration(self):
        FrameworkDimension = self.apps.get_model('comet', 'frameworkdimension')
        IndicatorFrameworkDimensionsThrough = self.apps.get_model('comet', 'indicatorframeworkdimensionsthrough')
        fd = FrameworkDimension.objects.last()
        fd_parent = FrameworkDimension.objects.get(name="Test FrameworkDimension Parent")
        ifdt = IndicatorFrameworkDimensionsThrough.objects.last()
        self.assertEqual(ifdt.frameworkdimension, fd)   # Check that new foreign key is working.
        self.assertEqual(fd.parent, fd_parent)  # Check that new foreign key is working.

        # The new fields are foreign key (relation) fields:
        self.assertTrue(IndicatorFrameworkDimensionsThrough._meta.get_field('frameworkdimension').is_relation)
        self.assertTrue(FrameworkDimension._meta.get_field('parent').is_relation)

        self.assertEqual(ifdt.frameworkdimension.uuid, fd.uuid)
        self.assertEqual(fd.parent.uuid, fd_parent.uuid)
