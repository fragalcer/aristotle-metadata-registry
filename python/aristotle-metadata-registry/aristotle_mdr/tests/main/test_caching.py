from django.test import TestCase
from django.contrib.contenttypes.models import ContentType

import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
from aristotle_mdr.utils.cache import recache_types
from aristotle_mdr.utils.cached_querysets import get_queryset_from_uuid, register_queryset
from django.contrib.auth import get_user_model

import datetime
from time import sleep


class CachingForRawPermissions(TestCase):

    def setUp(self):
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")
        self.ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        self.wg = models.Workgroup.objects.create(name="Test WG 1", stewardship_organisation=self.steward_org_1)
        self.wg.registrationAuthorities=[self.ra]
        self.wg.save()
        self.submitter = get_user_model().objects.create_user('suzie@example.com', 'submitter')
        self.wg.giveRoleToUser('submitter', self.submitter)
        self.item = models.ObjectClass.objects.create(name="Test OC1", workgroup=self.wg)

    def test_can_edit_cache(self):
        self.assertTrue(perms.user_can_edit(self.submitter, self.item))
        self.item.definition = "edit name, then quickly check permission"
        self.item.save()
        self.assertTrue(perms.user_can_edit(self.submitter, self.item))
        self.item.definition = "edit name, then wait 30 secs for 'recently edited to expire'"
        self.item.save()
        sleep(models.VERY_RECENTLY_SECONDS + 2)
        self.assertTrue(perms.user_can_edit(self.submitter, self.item))
        # register then immediately check the permissions to make sure the cache is ignored
        # technically we haven't edited the item yet, although ``concept.recache_states`` will be called.
        reg, c = models.Status.objects.get_or_create(
            concept=self.item,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2009, 4, 28),
            state=models.STATES.standard
        )
        self.assertFalse(perms.user_can_edit(self.submitter, self.item))

    def test_can_view_cache(self):
        self.viewer = get_user_model().objects.create_user('vicky@example.com', 'viewer')  # Don't need to assign any workgroups

        self.assertTrue(perms.user_can_view(self.submitter, self.item))
        self.assertFalse(perms.user_can_view(self.viewer, self.item))
        self.item.definition = "edit name, then quickly check permission"
        self.item.save()
        self.assertTrue(perms.user_can_view(self.submitter, self.item))
        self.assertFalse(perms.user_can_view(self.viewer, self.item))
        self.item.definition = "edit name, then wait 30 secs for 'recently edited to expire'"
        self.item.save()
        sleep(models.VERY_RECENTLY_SECONDS + 2)
        self.assertTrue(perms.user_can_view(self.submitter, self.item))
        self.assertFalse(perms.user_can_view(self.viewer, self.item))
        # register then immediately check the permissions to make sure the cache is ignored
        # technically we haven't edited the item yet, although ``concept.recache_states`` will be called.
        reg, c = models.Status.objects.get_or_create(
            concept=self.item,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2009, 4, 28),
            state=models.STATES.standard
        )
        self.assertTrue(perms.user_can_view(self.submitter, self.item))
        self.assertTrue(perms.user_can_view(self.viewer, self.item))


class TypeCachingTests(TestCase):

    def setUp(self):
        self.oc_ct = ContentType.objects.get_for_model(models.ObjectClass)

    def create_oc(self):
        return models.ObjectClass.objects.create(
            name='New Item',
            definition='So very new'
        )

    def test_type_caching_new_items(self):
        oc = self.create_oc()

        concept = oc._concept_ptr
        self.assertEqual(concept._type, self.oc_ct)

    def test_type_caching_bulk_update(self):
        oc1 = models.ObjectClass.objects.create(name='OC1', definition='Object Class number 1')
        oc2 = models.ObjectClass.objects.create(name='OC2', definition='Object Class number 2')
        co1 = oc1._concept_ptr
        co2 = oc2._concept_ptr
        # Reset _type
        models._concept.objects.all().update(_type=None)
        co1.refresh_from_db()
        co2.refresh_from_db()
        # Make sure _type was reset
        self.assertIsNone(oc1._type)
        self.assertIsNone(oc2._type)

        updated = recache_types()
        # Make sure some app labels were returned
        self.assertGreater(len(updated), 0)

        co1.refresh_from_db()
        co2.refresh_from_db()

        self.assertEqual(co1._type, self.oc_ct)
        self.assertEqual(co2._type, self.oc_ct)

    def test_cached_item(self):
        oc = self.create_oc()
        concept = oc._concept_ptr

        cached_item = concept.cached_item

        self.assertIsNotNone(cached_item)
        self.assertEqual(cached_item, oc)


class TestQuerySetCaching(TestCase):
    def setUp(self):
        self.oc = models.ObjectClass.objects.create(name="Object Class",
                                                    definition="Object Class")

        self.concept = models._concept.objects.create(name="Concrete concept",
                                                      definition="Concrete concept")

    @staticmethod
    def pickle_and_unpickle_queryset(concept):
        Model = type(concept)

        queryset = Model.objects.filter(id=concept.id)

        # Register it
        uuid = register_queryset(queryset)

        # Pull it from the cache
        unpickled_queryset = get_queryset_from_uuid(uuid, models.ObjectClass)

        return queryset, unpickled_queryset

    def test_pickling_and_unpickling_queryset_works_with_abstract_intermediate_model(self):
        # For object class
        original_queryset, unpickled_queryset = self.pickle_and_unpickle_queryset(self.oc)
        self.assertCountEqual(original_queryset, unpickled_queryset)
        # For _concept
        original_queryset, unpickled_queryset = self.pickle_and_unpickle_queryset(self.concept)
        self.assertCountEqual(original_queryset, unpickled_queryset)




