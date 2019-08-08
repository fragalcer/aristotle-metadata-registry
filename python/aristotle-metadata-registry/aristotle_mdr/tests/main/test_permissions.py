from django.contrib.auth import get_user_model
from django.test import TestCase

import datetime
from unittest import skip

import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
from aristotle_mdr.tests import utils


class SuperuserPermissions(TestCase):
    """
    All of the below are called with None as a Superuser, by definition *must* be able to edit, view and managed everything.
    Since a is_superuser check is cheap is should be called first, so calling with None
    checks that there is no other database calls going on.
    """
    def setUp(self):
        super().setUp()
        self.su=get_user_model().objects.create_superuser('super@example.com','user')
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

    def test_user_can_alter_comment(self):
        self.assertTrue(perms.user_can_alter_comment(self.su,None))

    def test_user_can_alter_post(self):
        self.assertTrue(perms.user_can_alter_post(self.su,None))

    def test_can_view(self):
        self.assertTrue(perms.user_can_view(self.su,None))

    def test_is_editor(self):
        self.assertTrue(perms.user_is_editor(self.su))

    def test_is_registrar(self):
        self.assertTrue(perms.user_is_registrar(self.su))

        ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        self.assertTrue(perms.user_is_registrar(self.su,ra))

    def test_is_workgroup_manager(self):
        wg = models.Workgroup.objects.create(name="Test WG", stewardship_organisation=self.steward_org_1)
        self.assertTrue(perms.user_is_workgroup_manager(self.su,wg))

    def test_can_change_status(self):
        self.assertTrue(perms.user_can_add_status(self.su,None))

    def test_can_edit(self):
        self.assertTrue(perms.user_can_edit(self.su,None))

    def test_in_workgroup(self):
        self.assertTrue(perms.user_in_workgroup(self.su,None))

    def test_can_edit_registration_authority(self):
        ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        self.assertTrue(ra.can_edit(self.su))


class UnitOfMeasureVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.UnitOfMeasure.objects.create(name="Test UOM",workgroup=self.wg)


class ObjectClassVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.ObjectClass.objects.create(name="Test OC",workgroup=self.wg)


class PropertyVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.Property.objects.create(name="Test P",workgroup=self.wg)


class ValueDomainVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.ValueDomain.objects.create(
            name="Test VD",
            workgroup=self.wg,
            format="X" ,
            maximum_length=3,
            data_type=models.DataType.objects.create(name="Test DT", workgroup=self.wg)
        )


class DataElementConceptVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.DataElementConcept.objects.create(
            name="Test DEC",
            workgroup=self.wg,
        )


class DataElementVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.DataElement.objects.create(
            name="Test DE",
            workgroup=self.wg,
        )


class DataTypeVisibility(utils.ManagedObjectVisibility,TestCase):
    def setUp(self):
        super().setUp()
        self.item = models.DataType.objects.create(
            name="Test DT",
            workgroup=self.wg,
        )


class WorkgroupPermissions(TestCase):
    def setUp(self):
        super().setUp()
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

    def test_workgroup_add_members(self):
        wg = models.Workgroup.objects.create(name="Test WG", stewardship_organisation=self.steward_org_1)
        user = get_user_model().objects.create_user('user@example.com','user')

        wg.giveRoleToUser('manager',user)
        self.assertTrue(wg.has_role('manager', user))
        wg.removeRoleFromUser('manager',user)
        self.assertFalse(wg.has_role('manager', user))

        wg.giveRoleToUser('viewer',user)
        self.assertTrue(wg.has_role('viewer', user))
        wg.removeRoleFromUser('viewer',user)
        self.assertFalse(wg.has_role('viewer', user))

        wg.giveRoleToUser('submitter',user)
        self.assertTrue(wg.has_role('submitter', user))
        wg.removeRoleFromUser('submitter',user)
        self.assertFalse(wg.has_role('submitter', user))

        wg.giveRoleToUser('steward',user)
        self.assertTrue(wg.has_role('steward', user))
        wg.removeRoleFromUser('steward',user)
        self.assertFalse(wg.has_role('steward', user))


class RegistryGroupPermissions(TestCase):
    def setUp(self):
        super().setUp()
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

    def test_registration_add_members(self):
        ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        user = get_user_model().objects.create_user('user@example.com','user')

        ra.giveRoleToUser('registrar',user)
        self.assertTrue(user in ra.registrars.all())
        ra.removeRoleFromUser('registrar',user)
        self.assertFalse(user in ra.registrars.all())

        ra.giveRoleToUser('manager',user)
        self.assertTrue(user in ra.managers.all())
        ra.removeRoleFromUser('manager',user)
        self.assertFalse(user in ra.managers.all())

    def test_RegistrationAuthority_name_change(self):
        ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        user = get_user_model().objects.create_user('registrar@example.com','registrar')

        # User isn't in RA... yet
        self.assertFalse(perms.user_is_registrar(user,ra))

        # Add user to RA, assert user is in RA
        ra.giveRoleToUser('registrar',user)
        # Caching issue, refresh from DB with correct permissions
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(perms.user_is_registrar(user,ra))

        # Change name of RA, assert user is still in RA
        ra.name = "Test RA2"
        ra.save()
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(perms.user_is_registrar(user,ra))

        # Add new RA with old RA's name, assert user is not in the new RA
        newRA = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        user = get_user_model().objects.get(pk=user.pk)
        self.assertFalse(perms.user_is_registrar(user,newRA))

        # Remove user to RA, assert user is no longer in RA
        ra.removeRoleFromUser('registrar',user)
        # Caching issue, refresh from DB with correct permissions
        user = get_user_model().objects.get(pk=user.pk)
        self.assertFalse(perms.user_is_registrar(user,ra))


class UserEditTesting(TestCase):
    def test_canViewProfile(self):
        u1 = get_user_model().objects.create_user('user1@example.com','user1')
        u2 = get_user_model().objects.create_user('user2@example.com','user2')
        self.assertFalse(perms.user_can_view(u1,u2))
        self.assertFalse(perms.user_can_view(u2,u1))
        self.assertTrue(perms.user_can_view(u1,u1))
        self.assertTrue(perms.user_can_view(u2,u2))
    def test_canEditProfile(self):
        u1 = get_user_model().objects.create_user('user1@example.com','user1')
        u2 = get_user_model().objects.create_user('user2@example.com','user2')
        self.assertFalse(perms.user_can_edit(u1,u2))
        self.assertFalse(perms.user_can_edit(u2,u1))
        self.assertTrue(perms.user_can_edit(u1,u1))
        self.assertTrue(perms.user_can_edit(u2,u2))


class CustomConceptQuerySetTest(TestCase):
    def setUp(self):
        super().setUp()
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

    def test_is_public_as_changes_happen(self):
        # Uses ValueDomain so the querysets don't return things created in `setUpClass`.
        ra = models.RegistrationAuthority.objects.create(name="Test RA", public_state=models.STATES.standard, stewardship_organisation=self.steward_org_1)
        wg = models.Workgroup.objects.create(name="Setup WG", stewardship_organisation=self.steward_org_1)
        wg.save()
        oc1 = models.ValueDomain.objects.create(name="Test OC1",workgroup=wg)
        oc2 = models.ValueDomain.objects.create(name="Test OC2",workgroup=wg)
        user = get_user_model().objects.create_superuser('super@example.com','user')

        # Assert no public items
        self.assertEqual(len(models.ValueDomain.objects.all().public()),0)

        # Register OC1 only
        ra.register(oc1,models.STATES.standard,user,effective_date=datetime.date(2010,10,1))

        # Assert only OC1 is public
        self.assertEqual(len(models.ValueDomain.objects.all().public()),1)
        self.assertTrue(oc1 in models.ValueDomain.objects.all().public())
        self.assertTrue(oc2 not in models.ValueDomain.objects.all().public())

        from time import sleep
        sleep(2)
        # Sleep for 2 seconds, as MMSQL is seeing both registrations as having the 'same' creation time

        # Deregister OC1
        state=models.STATES.incomplete
        regDate=datetime.date(2010,10,1)
        registration_attempt = ra.register(oc1,state,user,effective_date=regDate)

        oc1 = models.ValueDomain.objects.get(pk=oc1.pk)

        self.assertTrue(registration_attempt['failed'] == [])
        self.assertTrue(len(oc1.current_statuses()) == 1)
        self.assertTrue(oc1.current_statuses().first().effective_date == regDate)
        self.assertFalse(oc1._is_public)

        # Assert no public items
        self.assertTrue(oc1 not in models.ValueDomain.objects.all().public())
        self.assertEqual(len(models.ValueDomain.objects.all().public()),0)


class RegistryCascadeTest(TestCase):
    def setUp(self):
        super().setUp()
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

    def test_superuser_DataElementConceptCascade(self):
        user = get_user_model().objects.create_superuser('super@example.com','user')
        self.ra = models.RegistrationAuthority.objects.create(name="Test RA - cascading", stewardship_organisation=self.steward_org_1)
        self.wg = models.Workgroup.objects.create(name="Setup WG", stewardship_organisation=self.steward_org_1)
        self.wg.save()
        self.oc = models.ObjectClass.objects.create(name="Test OC",workgroup=self.wg)
        self.pr = models.Property.objects.create(name="Test P",workgroup=self.wg)
        self.dec = models.DataElementConcept.objects.create(
            name="Test DEC",
            objectClass=self.oc,
            property=self.pr,
            workgroup=self.wg,
        )

        self.assertEqual(self.oc.statuses.count(),0)
        self.assertEqual(self.pr.statuses.count(),0)
        self.assertEqual(self.dec.statuses.count(),0)

        state=models.STATES.candidate
        self.ra.register(self.dec,state,user,effective_date=datetime.date(2001,10,1),changeDetails='test DEC register')
        self.assertEqual(self.oc.statuses.count(),0)
        self.assertEqual(self.pr.statuses.count(),0)
        self.assertEqual(self.dec.statuses.count(),1)

        state=models.STATES.standard
        self.ra.cascaded_register(self.dec,state,user,effective_date=datetime.date(2010,10,1),changeDetails='test DEC cascade register')
        self.assertEqual(len(self.dec.current_statuses()),1)
        self.assertEqual(len(self.oc.current_statuses()),1)
        self.assertEqual(len(self.pr.current_statuses()),1)

        self.assertEqual(self.oc.current_statuses()[0].state,state)
        self.assertEqual(self.pr.current_statuses()[0].state,state)
        self.assertEqual(self.dec.current_statuses()[0].state,state)

    def test_superuser_DataElementCascade(self):
        user = get_user_model().objects.create_superuser('super@example.com','user')
        self.ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)
        self.wg = models.Workgroup.objects.create(name="Setup WG", stewardship_organisation=self.steward_org_1)
        self.wg.save()
        self.oc = models.ObjectClass.objects.create(name="Test OC",workgroup=self.wg)
        self.pr = models.Property.objects.create(name="Test P",workgroup=self.wg)
        self.vd = models.ValueDomain.objects.create(
            name="Test VD",
            workgroup=self.wg,
            format = "X" ,
            maximum_length = 3,
            data_type = models.DataType.objects.create(name="Test DT",workgroup=self.wg)
        )
        self.dec = models.DataElementConcept.objects.create(
            name="Test DEC",
            objectClass=self.oc,
            property=self.pr,
            workgroup=self.wg,
        )
        self.de = models.DataElement.objects.create(
            name="Test DE",
            dataElementConcept=self.dec,
            valueDomain=self.vd,
            workgroup=self.wg,
        )

        self.assertEqual(self.oc.statuses.count(),0)
        self.assertEqual(self.pr.statuses.count(),0)
        self.assertEqual(self.vd.statuses.count(),0)
        self.assertEqual(self.dec.statuses.count(),0)
        self.assertEqual(self.de.statuses.count(),0)

        state=models.STATES.candidate
        self.ra.register(self.de,state,user,effective_date=datetime.date(2001,10,1),)
        self.assertEqual(len(self.oc.current_statuses()),0)
        self.assertEqual(len(self.pr.current_statuses()),0)
        self.assertEqual(len(self.vd.current_statuses()),0)
        self.assertEqual(len(self.dec.current_statuses()),0)
        self.assertEqual(len(self.de.current_statuses()),1)

        state=models.STATES.standard
        self.ra.cascaded_register(self.de,state,user,effective_date=datetime.date(2010,10,1),)
        self.assertEqual(len(self.de.current_statuses()),1)
        self.assertEqual(len(self.dec.current_statuses()),1)
        self.assertEqual(len(self.vd.current_statuses()),1)
        self.assertEqual(len(self.oc.current_statuses()),1)
        self.assertEqual(len(self.pr.current_statuses()),1)

        self.assertEqual(self.oc.current_statuses()[0].state,state)
        self.assertEqual(self.pr.current_statuses()[0].state,state)
        self.assertEqual(self.vd.current_statuses()[0].state,state)
        self.assertEqual(self.dec.current_statuses()[0].state,state)
        self.assertEqual(self.de.current_statuses()[0].state,state)


# TODO: put this back in
@skip("We shifted stuff around, and workgroups now use more, but faster queries")
class PermsEfficiencyTestCase(utils.AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.oc = models.ObjectClass.objects.create(
            name='Things',
            definition='A class of thing',
            submitter=self.editor
        )

    def test_visible_efficiency(self):
        # Currently 2 because of is_registrar check
        with self.assertNumQueries(2):
            models.ObjectClass.objects.visible(self.editor).first()

    def test_user_can_view_efficiency(self):
        # Currently 2 because of is_registrar check
        with self.assertNumQueries(2):
            perms.user_can_view(self.editor, self.oc)
