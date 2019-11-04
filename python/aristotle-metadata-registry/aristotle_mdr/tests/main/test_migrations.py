from aristotle_mdr import models
from aristotle_mdr.contrib.slots import models as slots_models
from aristotle_mdr.tests.migrations import MigrationsTestCase
from aristotle_mdr.utils import migrations as migration_utils

from django.test import TestCase
from django.apps import apps as current_apps


class TestUtils(TestCase):

    def test_forward_slot_move(self):
        oc1 = models.ObjectClass.objects.create(
            name='Test OC',
            definition='Test Definition',
            version='1.11.1'
        )

        oc2 = models.ObjectClass.objects.create(
            name='Test Blank OC',
            definition='Test Definition'
        )

        migration_utils.move_field_to_slot(current_apps, None, 'version')

        self.assertEqual(oc1.slots.count(), 1)
        self.assertEqual(oc2.slots.count(), 0)

        slots = oc1.slots.all()

        self.assertEqual(slots[0].name, 'version')
        self.assertEqual(slots[0].value, '1.11.1')

    def test_backwards_slot_move(self):
        oc1 = models.ObjectClass.objects.create(
            name='Test OC',
            definition='Test Definition',
            version=''
        )

        slot1 = slots_models.Slot.objects.create(
            name='version',
            concept=oc1,
            value='2.222'
        )

        slot2 = slots_models.Slot.objects.create(
            name='otherslot',
            concept=oc1,
            value='othervalue'
        )

        migration_utils.move_slot_to_field(current_apps, None, 'version')

        # Have to get from db again
        oc1 = models.ObjectClass.objects.get(id=oc1.id)
        self.assertEqual(oc1.version, '2.222')


class TestLinkRootMigration(MigrationsTestCase, TestCase):
    app = 'aristotle_mdr_links'
    migrate_from = '0006_link_root_item'
    migrate_to = '0007_migrate_root_item'

    def setUpBeforeMigration(self, apps):
        objectclass = apps.get_model('aristotle_mdr', 'ObjectClass')
        relation = apps.get_model('aristotle_mdr_links', 'Relation')
        relation_role = apps.get_model('aristotle_mdr_links', 'RelationRole')

        link = apps.get_model('aristotle_mdr_links', 'Link')
        linkend = apps.get_model('aristotle_mdr_links', 'LinkEnd')

        self.item1 = objectclass.objects.create(
            name='Item1',
            definition='Item1'
        )
        self.item2 = objectclass.objects.create(
            name='Item2',
            definition='Item2'
        )

        self.relation = relation.objects.create(
            name='Good relation',
            definition='Very good'
        )
        rr1 = relation_role.objects.create(
            name='First item',
            definition='First',
            ordinal=1,
            relation=self.relation
        )
        rr2 = relation_role.objects.create(
            name='Second item',
            definition='Second',
            ordinal=2,
            relation=self.relation
        )

        self.link = link.objects.create(
            relation=self.relation
        )
        linkend1 = linkend.objects.create(
            link=self.link,
            role=rr1,
            concept=self.item1._concept_ptr
        )
        linkend1 = linkend.objects.create(
            link=self.link,
            role=rr2,
            concept=self.item2._concept_ptr
        )

    def test_migration(self):
        link_model = self.apps.get_model('aristotle_mdr_links', 'Link')
        link = link_model.objects.get(id=self.link.id)
        self.assertEqual(link.root_item.id, self.item1.id)

