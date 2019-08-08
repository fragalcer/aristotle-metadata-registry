from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from datetime import timedelta

from aristotle_mdr import models as mdr_models
from aristotle_mdr import perms
from aristotle_mdr import models
from aristotle_mdr.models import StewardOrganisation
from aristotle_mdr.tests import utils

User = get_user_model()


class BaseStewardOrgsTestCase(utils.AristotleTestUtils):
    def setUp(self):
        super().setUp()

        self.regular_org = StewardOrganisation.objects.create(
            name='Regular Org',
            description="2",
            state=StewardOrganisation.states.active
        )
        self.private_org = StewardOrganisation.objects.create(
            name='Private Org',
            description="2",
            state=StewardOrganisation.states.private
        )

        self.oscar = User.objects.create(
            email="oscar@aristotle.example.com",
            short_name="Oscar"
        )
        self.regular_org.grant_role(
            role=StewardOrganisation.roles.member,
            user=self.oscar,
        )
        self.pyle = User.objects.create(
            email="pvt.pyle@aristotle.example.mil",
            short_name="Gomer"
        )
        self.private_org.grant_role(
            role=StewardOrganisation.roles.member,
            user=self.pyle,
        )

        self.assertTrue(
            self.regular_org.has_role(
                role=StewardOrganisation.roles.member,
                user=self.oscar,
            )
        )
        self.assertTrue(
            self.private_org.has_role(
                role=StewardOrganisation.roles.member,
                user=self.pyle,
            )
        )
        self.private_wg = models.Workgroup.objects.create(
            name="Private WG",
            stewardship_organisation=self.private_org,
        )
        self.regular_wg = models.Workgroup.objects.create(
            name="Public WG",
            stewardship_organisation=self.regular_org,
        )
        self.private_ra = models.RegistrationAuthority.objects.create(
            name="Private RA",
            stewardship_organisation=self.private_org,
        )
        self.regular_ra = models.RegistrationAuthority.objects.create(
            name="Public RA",
            stewardship_organisation=self.regular_org,
        )
        self.private_oc = models.ObjectClass.objects.create(
            name="Private OC",
            stewardship_organisation=self.private_org,
            workgroup=self.private_wg,
        )
        self.regular_oc = models.ObjectClass.objects.create(
            name="Public OC",
            stewardship_organisation=self.regular_org,
            workgroup=self.regular_wg,
        )


class TestPrivatePermissions(BaseStewardOrgsTestCase, TestCase):
    def test_metadata_permissions(self):
        self.assertTrue(
            self.private_oc not in models.ObjectClass.objects.all().visible(self.oscar)    
        )
        self.assertTrue(
            self.regular_oc not in models.ObjectClass.objects.all().visible(self.oscar)    
        )
        self.assertTrue(
            self.private_oc not in models.ObjectClass.objects.all().visible(self.pyle)    
        )
        self.assertTrue(
            self.regular_oc not in models.ObjectClass.objects.all().visible(self.pyle)    
        )

        self.private_ra.register(
            item=self.private_oc,
            state=models.STATES.standard,
            user=self.su,
            effective_date=(timezone.now()-timedelta(days=5)).date()
        )
        self.regular_ra.register(
            item=self.regular_oc,
            state=models.STATES.standard,
            user=self.su,
            effective_date=(timezone.now()-timedelta(days=5)).date()
        )
        self.private_ra.register(
            item=self.regular_oc,
            state=models.STATES.standard,
            user=self.su,
            effective_date=(timezone.now()-timedelta(days=5)).date()
        )
        self.regular_ra.register(
            item=self.private_oc,
            state=models.STATES.standard,
            user=self.su,
            effective_date=(timezone.now()-timedelta(days=5)).date()
        )

        self.assertTrue(
            self.private_oc not in models.ObjectClass.objects.all().visible(None)    
        )
        self.assertTrue(
            self.regular_oc in models.ObjectClass.objects.all().visible(None)    
        )
        self.assertTrue(
            self.private_oc in models.ObjectClass.objects.all().visible(self.pyle)    
        )
        self.assertTrue(
            self.regular_oc in models.ObjectClass.objects.all().visible(self.pyle)    
        )
        self.assertTrue(
            self.regular_oc in models.ObjectClass.objects.all().visible(self.oscar)    
        )
        self.assertTrue(
            self.private_oc not in models.ObjectClass.objects.all().visible(self.oscar)    
        )

    def test_ra_permissions(self):
        RA = models.RegistrationAuthority
        self.assertTrue(
            self.oscar not in self.private_ra.stewardship_organisation.member_list
        )
        self.assertTrue(
            self.private_ra not in RA.objects.all().visible(self.oscar)    
        )
        self.assertTrue(
            self.regular_ra in RA.objects.all().visible(self.oscar)    
        )
        self.assertTrue(
            self.private_ra in RA.objects.all().visible(self.pyle)    
        )
        self.assertTrue(
            self.regular_ra in RA.objects.all().visible(self.pyle)
        )
