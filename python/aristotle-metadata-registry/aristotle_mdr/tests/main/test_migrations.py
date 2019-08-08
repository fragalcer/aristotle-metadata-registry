from aristotle_mdr import models
from aristotle_mdr.contrib.slots import models as slots_models
from aristotle_mdr.models import STATES
from aristotle_mdr.tests.migrations import MigrationsTestCase
from aristotle_mdr.utils import migrations as migration_utils

from django.test import TestCase, tag
from django.apps import apps as current_apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest import skip


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


class TestSynonymMigration(MigrationsTestCase, TestCase):

    migrate_from = '0023_auto_20180206_0332'
    migrate_to = '0024_synonym_data_migration'

    def setUpBeforeMigration(self, apps):
        objectclass = apps.get_model('aristotle_mdr', 'ObjectClass')

        self.oc1 = objectclass.objects.create(
            name='Test OC',
            definition='Test Definition',
            synonyms='great'
        )

        self.oc2 = objectclass.objects.create(
            name='Test Blank OC',
            definition='Test Definition'
        )

    def test_migration(self):

        slot = self.apps.get_model('aristotle_mdr_slots', 'Slot')

        self.assertEqual(slot.objects.count(), 1)

        syn_slot = slot.objects.get(name='Synonyms')
        self.assertEqual(syn_slot.concept.name, self.oc1.name)
        self.assertEqual(syn_slot.concept.definition, self.oc1.definition)
        self.assertEqual(syn_slot.value, 'great')

#class TestSynonymMigrationReverse(MigrationsTestCase, TestCase):
#
#    migrate_from = '0024_synonym_data_migration'
#    migrate_to = '0023_auto_20180206_0332'
#
#    def setUpBeforeMigration(self, apps):
#        objectclass = apps.get_model('aristotle_mdr', 'ObjectClass')
#        slot = apps.get_model('aristotle_mdr_slots', 'Slot')
#
#        self.oc = objectclass.objects.create(
#            name='Test OC',
#            definition='Test Definition',
#            synonyms='great'
#        )
#
#        self.slot = slot.objects.create(
#            name='Synonyms',
#            concept=self.oc,
#            value='amazing'
#        )
#
#    def test_migration(self):
#
#        objectclass = self.apps.get_model('aristotle_mdr', 'ObjectClass')
#
#        oc = objectclass.objects.get(pk=self.oc.pk)
#        self.assertEqual(oc.synonyms, 'amazing')

class TestDedMigration(MigrationsTestCase, TestCase):

    migrate_from = '0026_auto_20180411_2323'
    #migrate_to = '0028_replace_old_ded_through'
    migrate_to = '0027_add_ded_through_models'

    def setUpBeforeMigration(self, apps):

        ded = apps.get_model('aristotle_mdr', 'DataElementDerivation')
        de = apps.get_model('aristotle_mdr', 'DataElement')

        self.ded1 = ded.objects.create(
            name='DED1',
            definition='test defn',
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

        self.ded1.derives.add(self.de1)
        self.ded1.derives.add(self.de2)
        self.ded1.inputs.add(self.de3)

    def test_migration(self):

        ded = self.apps.get_model('aristotle_mdr', 'DataElementDerivation')
        ded_inputs_through = self.apps.get_model('aristotle_mdr', 'DedInputsThrough')
        ded_derives_through = self.apps.get_model('aristotle_mdr', 'DedDerivesThrough')

        ded_obj = ded.objects.get(pk=self.ded1.pk)

        # Test through objects order

        items = ded_inputs_through.objects.filter(data_element_derivation=ded_obj)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.order, 0)
        self.assertEqual(item.data_element.pk, self.de3.pk)

        items = ded_derives_through.objects.filter(data_element_derivation=ded_obj).order_by('order')
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].order, 0)
        self.assertEqual(items[1].order, 1)

        de_pks = [item.data_element.pk for item in items]
        orig_de_pks = [self.de1.pk, self.de2.pk]

        self.assertEqual(set(de_pks), set(orig_de_pks))


class TestLowercaseEmailMigration(MigrationsTestCase, TestCase):

    app = 'aristotle_mdr_user_management'
    migrate_from = '0001_initial'
    migrate_to = '0002_lowercase_emails'

    def setUpBeforeMigration(self, apps):
        user = apps.get_model('aristotle_mdr_user_management', 'User')

        user.objects.create(
            email='FIRST@example.com',
        )
        user.objects.create(
            email='Second@example.com',
        )

    def test_migration(self):
        user = self.apps.get_model('aristotle_mdr_user_management', 'User')
        self.assertEqual(user.objects.count(), 2)
        self.assertTrue(user.objects.filter(email='first@example.com').exists())
        self.assertTrue(user.objects.filter(email='second@example.com').exists())
        self.assertFalse(user.objects.filter(email='FIRST@example.com').exists())
        self.assertFalse(user.objects.filter(email='Second@example.com').exists())


class TestRaActiveMigration(MigrationsTestCase, TestCase):

    migrate_from = '0032_add_new_active'
    migrate_to = '0033_ra_levels'

    def setUpBeforeMigration(self, apps):

        ra = apps.get_model('aristotle_mdr', 'RegistrationAuthority')

        self.ra1 = ra.objects.create(
            name='ActiveRA',
            definition='defn',
            active=True
        )
        self.ra2 = ra.objects.create(
            name='InactiveRA',
            definition='defn',
            active=False
        )

    def test_migration(self):

        ra = self.apps.get_model('aristotle_mdr', 'RegistrationAuthority')
        from aristotle_mdr.models import RA_ACTIVE_CHOICES

        activera = ra.objects.get(name='ActiveRA')
        self.assertEqual(activera.new_active, RA_ACTIVE_CHOICES.active)

        inactivera = ra.objects.get(name='InactiveRA')
        self.assertEqual(inactivera.new_active, RA_ACTIVE_CHOICES.inactive)


@skip("Field added to Possum Profile (Notification Permissions).")
class TestSupersedingMigration(MigrationsTestCase, TestCase):

    migrate_from = '0042_remove_possumprofile_favourites'
    migrate_to = '0043_change_superseding'

    def setUpBeforeMigration(self, apps):
        objectclass = apps.get_model('aristotle_mdr', 'ObjectClass')
        registrationauthority = apps.get_model('aristotle_mdr', 'RegistrationAuthority')
        Status = apps.get_model('aristotle_mdr', 'Status')

        self.su = get_user_model().objects.create_superuser('super@example.com', 'user')

        self.oc_new = objectclass.objects.create(
            name='A newer OC',
            definition='Test Definition',
        )

        # This highlights how backwards we got it.
        # The old one has to be made *first*
        self.oc_old_1 = objectclass.objects.create(
            name='An older OC',
            definition='Test Definition. Superseded.',
            superseded_by=self.oc_new
        )

        self.oc_old_2 = objectclass.objects.create(
            name='An different older OC',
            definition='Test Definition. Not superseded',
            superseded_by=self.oc_new
        )

        self.ra = registrationauthority.objects.create(
            name='The RA',
            definition='Test Definition',
        )

        Status.objects.create(
            concept=self.oc_old_1,
            registrationAuthority=self.ra,
            effective_date=timezone.now().date(),
            state=STATES.superseded,
        )

        Status.objects.create(
            concept=self.oc_new,
            registrationAuthority=self.ra,
            effective_date=timezone.now().date(),
            state=STATES.standard,
        )
    def test_migration(self):
        objectclass = self.apps.get_model('aristotle_mdr', 'ObjectClass')
        self.oc_new = objectclass.objects.get(name='A newer OC')
        self.oc_old_1 = objectclass.objects.get(name='An older OC')
        self.oc_old_2 = objectclass.objects.get(name='An different older OC')

        self.assertEqual(
            self.oc_old_1.superseded_by_items_relation_set.all().first().newer_item.pk,
            self.oc_new.pk,
        )

        self.assertEqual(
            self.oc_old_2.superseded_by_items_relation_set.all().count(),
            0
        )


@tag('favsmigration')
class TestFavouritesMigration(MigrationsTestCase, TestCase):

    migrate_from='0040_rename_favourites'
    migrate_to='0041_migrate_favourites'

    def setUpBeforeMigration(self, apps):
        user = apps.get_model('aristotle_mdr_user_management', 'User')
        profile = apps.get_model('aristotle_mdr', 'PossumProfile')
        objectclass = apps.get_model('aristotle_mdr', 'ObjectClass')

        self.user = user.objects.create(
            email='wow@example.com',
        )
        # self.user.set_password('wow')

        self.item1 = objectclass.objects.create(
            name='Test Item',
            definition='Just a test'
        )

        self.profile = profile.objects.create(user=self.user)

        self.profile.old_favourites.add(self.item1._concept_ptr)

    def test_migration(self):
        tag = self.apps.get_model('aristotle_mdr_favourites', 'Tag')
        favourite = self.apps.get_model('aristotle_mdr_favourites', 'Favourite')

        self.assertTrue(tag.objects.filter(profile=self.profile.id, primary=True).exists())

        favtag = tag.objects.get(profile=self.profile.id, primary=True)

        itemfavs = favourite.objects.filter(tag=favtag, item=self.item1._concept_ptr.id)
        self.assertTrue(itemfavs.exists())
        self.assertEqual(itemfavs.count(), 1)


class TestLinkRootMigration(MigrationsTestCase, TestCase):

    app = 'aristotle_mdr_links'
    migrate_from = [
        ('aristotle_mdr','0046_auto_20181107_0433'),
        ('aristotle_mdr_links','0006_link_root_item'),
    ]
    migrate_to = [
        ('aristotle_mdr','0046_auto_20181107_0433'),
        ('aristotle_mdr_links','0007_migrate_root_item'),
    ]

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


class TestRAOrganisationRemoval(MigrationsTestCase, TestCase):

    app = 'aristotle_mdr'
    migrate_from = '0046_auto_20181107_0433'
    migrate_to = '0049_make_non_nullable_so'


    def setUpBeforeMigration(self, apps):
        User = apps.get_model('aristotle_mdr_user_management', 'User')
        RAClass = apps.get_model('aristotle_mdr', 'RegistrationAuthority')
        OrgClass = apps.get_model('aristotle_mdr', 'Organization')
        # StewardOrgClass = apps.get_model('aristotle_mdr', 'StewardOrganisation')

        # self.so = StewardOrgClass.objects.create(name="New SO")

        self.manager = User.objects.create(
            email='manager@example.com',
        )
        self.registrar = User.objects.create(
            email='registrar@example.com',
        )
        # self.org = OrgClass.objects.create(
        #     name='My RA',
        #     definition="",
        #     stewardship_organisation=self.so,
        # )
        self.ra = RAClass.objects.create(
            name='My RA',
            definition="",
            # stewardship_organisation=self.so,
            # organization_ptr = self.org, # Manually connect, because we fiddled with bases
            locked_state=3,
        )
        # self.org = self.ra.organization

    def test_migration(self):
        from django.apps import apps
        # OrgClass = apps.get_model('aristotle_mdr', 'Organization')
        RAClass = apps.get_model('aristotle_mdr', 'RegistrationAuthority')
        StewardOrgClass = apps.get_model('aristotle_mdr', 'StewardOrganisation')
        s_org = StewardOrgClass.objects.all().first()
        # user = self.apps.get_model('aristotle_mdr_user_management', 'User')
        # self.assertEqual(user.objects.count(), 2)
        # self.assertTrue(user.objects.filter(email='first@example.com').exists())
        # self.org.refresh_from_db()
        # # self.org = OrgClass.objects.get(pk=self.org.pk)
        # # self.org.name = "My Org"
        # # self.org.save()
        # self.ra.refresh_from_db()

        # self.assertTrue(
        #     self.ra.created == self.org.created
        # )
        self.ra = RAClass.objects.get(pk=self.ra.pk)
        print(self.ra) #.stewardship_organisation)

        self.assertTrue(self.ra.stewardship_organisation == s_org)
