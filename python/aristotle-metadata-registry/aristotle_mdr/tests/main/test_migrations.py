from unittest import skip
from django.test import TestCase, tag
from django.apps import apps as current_apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from aristotle_mdr import models
from aristotle_mdr.contrib.slots import models as slots_models
from aristotle_mdr.models import STATES
from aristotle_mdr.tests.migration_test_utils import MigrationsTestCase
from aristotle_mdr.utils import migration_utils


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
