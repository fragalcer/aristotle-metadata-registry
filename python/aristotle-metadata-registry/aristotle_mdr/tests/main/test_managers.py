from django.test import TestCase
from django.contrib.auth import get_user_model
from aristotle_mdr import models
from aristotle_mdr.contrib.reviews.models import ReviewRequest

from datetime import date


class ConceptManagerTestCase(TestCase):

    def setUp(self):
        self.um = get_user_model()
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")
        self.user = self.um.objects.create_user(email='testuser@example.com', password='1234')
        self.ra = models.RegistrationAuthority.objects.create(
            name='MyRA', definition='mine',
            stewardship_organisation=self.steward_org_1
        )
        self.ra2 = models.RegistrationAuthority.objects.create(
            name='My2ndRA', definition='mine',
            stewardship_organisation=self.steward_org_1
        )
        # Test item
        self.item = models.ObjectClass.objects.create(
            name='Thingys',
            definition='You know, one a them thingos',
            submitter=self.user,
        )

    def test_visible_distinct_multiple_ras(self):
        """
        Test an item doesnt appear twice if registered in 2 ras
        if user is registrar in both
        """
        # Make user a registrar in both ras
        self.ra.registrars.add(self.user)
        self.ra2.registrars.add(self.user)
        # Register item in both ras
        status = models.Status.objects.create(
            registrationAuthority=self.ra,
            concept=self.item.concept,
            effective_date=date(2001, 1, 1),
            state=models.STATES.standard
        )
        status2 = models.Status.objects.create(
            registrationAuthority=self.ra2,
            concept=self.item.concept,
            effective_date=date(2001, 1, 1),
            state=models.STATES.standard
        )
        # Make sure user is considered a registrar
        self.assertTrue(self.user.profile.is_registrar)
        # Get visible concepts to user
        visible = models._concept.objects.visible(self.user)
        # Make sure it only appers once
        self.assertEqual(visible.count(), 1)

    def test_visible_distinct_rr_and_status(self):
        """
        Test an item doesnt appear twice if being reviewed and registered in 1 ra
        """
        # Make user registrar in ra1 only
        self.ra.registrars.add(self.user)
        # Register item
        status = models.Status.objects.create(
            registrationAuthority=self.ra,
            concept=self.item.concept,
            effective_date=date(2001, 1, 1),
            state=models.STATES.standard
        )
        # Create review request for item
        rr = ReviewRequest.objects.create(
            registration_authority=self.ra,
            requester=self.user,
        )
        # Get visible concepts to user
        visible = models._concept.objects.visible(self.user)
        # Make sure it only appers once
        self.assertEqual(visible.count(), 1)

    def test_visible_distinct_wg_and_ra(self):
        """
        Test an item doesnt appear twice if in users wg and ra
        """
        # Make user wg manager
        wg = models.Workgroup.objects.create(
            name='MyWG', definition='mine',
            stewardship_organisation=self.steward_org_1
        )
        wg.giveRoleToUser('manager', self.user)
        # Add test item to wg
        self.item.workgroup = wg
        self.item.save()
        # Register item
        status = models.Status.objects.create(
            registrationAuthority=self.ra,
            concept=self.item.concept,
            effective_date=date(2001, 1, 1),
            state=models.STATES.standard
        )
        # Get visible concepts to user
        visible = models._concept.objects.visible(self.user)
        # Make sure it only appers once
        self.assertEqual(visible.count(), 1)
