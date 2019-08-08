from django.utils import timezone

from django.test import TestCase
from django.urls import reverse

from aristotle_mdr.tests.utils import AristotleTestUtils
from aristotle_mdr import models as MDR

import datetime


class AristotleReportingToolsPage(AristotleTestUtils, TestCase):
    url_name = 'data_element_components_tool'

    def setUp(self):
        super().setUp()

        self.login_superuser()

        self.property_non_std = MDR.Property.objects.create(
            name="My PROPERTY NON STANDARD",
            definition="My prop",
            workgroup=self.wg1,
        )

        self.status_prop_non_standard = MDR.Status.objects.create(
            concept=self.property_non_std,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        self.object_class_non_std = MDR.Property.objects.create(
            name="My OBJECT CLASS NON STANDARD",
            definition="My oc...",
            workgroup=self.wg1,
        )

        MDR.Status.objects.create(
            concept=self.object_class_non_std,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        self.dec_non_std = MDR.DataElementConcept.objects.create(
            name="My DEC",
            definition="MY dec...",
            workgroup=self.wg1,
            property=self.property_non_std
        )

        MDR.Status.objects.create(
            concept=self.property_non_std,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        self.vd_non_std = MDR.ValueDomain.objects.create(
            name="My Value Domain",
            definition="My vd...",
            workgroup=self.wg1,
        )

        MDR.Status.objects.create(
            concept=self.vd_non_std,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        self.de_std = MDR.DataElement.objects.create(
            name="My Data Element",
            definition="My data elem...",
            workgroup=self.wg1,
            valueDomain=self.vd_non_std,
        )

        MDR.Status.objects.create(
            concept=self.de_std,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.standard,
        )

        self.logout()

    def test_there_is_only_one_standard_data_element(self):

        standard_status = '5'

        response = self.client.get(
            reverse(
                'aristotle:data_element_components_tool') + '?ra=' + str(self.ra.id) + '&status=' + standard_status
        )

        self.assertEqual(response.context['object_list'].count(), 1)

    def test_query_only_returns_data_elements_with_components(self):

        incomplete_status = '1'

        my_data_element = MDR.DataElement.objects.create(
            name="My lonely data element",
            definition="I am so lonely. I have no subcomponents.",
            workgroup=self.wg1,
        )

        my_status_for_lonely_data_element = MDR.Status.objects.create(
            concept=my_data_element,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.incomplete,
        )

        response = self.client.get(
            reverse(
                'aristotle:data_element_components_tool') + '?ra=' + str(self.ra.id) + '&status=' + incomplete_status
        )

        self.assertEqual(response.context['object_list'].count(), 0)

    def test_query_only_fetches_data_elements_with_components_with_different_statuses(self):

        qualified_status = '4'

        data_element_concept_for_de_qualified = MDR.DataElementConcept.objects.create(
            name="MY DEC for DE Qualified.",
            definition="mY DEC",
            workgroup=self.wg1,
        )

        de_qualified = MDR.DataElement.objects.create(
            name="My Qualified Data Element",
            definition="My non standard data elem...",
            workgroup=self.wg1,
            dataElementConcept=data_element_concept_for_de_qualified,
        )

        # Same Status!
        MDR.Status.objects.create(
            concept=de_qualified,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        # Same Status!
        MDR.Status.objects.create(
            concept=data_element_concept_for_de_qualified,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=MDR.STATES.qualified,
        )

        response = self.client.get(
            reverse(
                'aristotle:data_element_components_tool') + '?ra=' + str(self.ra.id) + '&status=' + qualified_status
        )

        self.assertEqual(response.context['object_list'].count(), 0)

    def test_data_elements_fetched_correspond_to_the_right_ra(self):

        prefered_status = '6'

        another_ra = MDR.RegistrationAuthority.objects.create(
            name="My second RA",
            definition="My second RA",
            stewardship_organisation=self.steward_org_1,
        )

        vd_for_data_element_with_second_ra = MDR.ValueDomain.objects.create(
            name="VD for data element with second ra",
            definition="My VD",
            workgroup=self.wg1,
        )

        data_element_with_second_ra = MDR.DataElement.objects.create(
            name="Data Element with another RA",
            definition="Data Element with another RA",
            workgroup=self.wg1,
            valueDomain=vd_for_data_element_with_second_ra
        )

        MDR.Status.objects.create(
            concept=data_element_with_second_ra,
            registrationAuthority=another_ra,
            effective_date=timezone.now(),
            state=MDR.STATES.preferred,
        )

        response = self.client.get(
            reverse(
                'aristotle:data_element_components_tool') + '?ra=' + str(another_ra.id) + '&status=' + prefered_status
        )
        self.assertEqual(response.context['object_list'].count(), 1)

    def test_correct_status_for_component_displayed(self):
        """Test that the correct status is displayed for components in the template"""
        # Create a Value Domain
        value_domain = MDR.ValueDomain.objects.create(
            name="Value Domain",
            definition="Value Domain",
            workgroup=self.wg1,
        )

        # Create a Data Element
        data_element = MDR.DataElement.objects.create(
            name=" Data Element",
            definition="A data element",
            workgroup=self.wg1,
            valueDomain=value_domain,
        )
        # Register the Data Element as Standard
        data_element = MDR.Status.objects.create(
            concept=data_element,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2017, 1, 1)
        )

        # Register the Value Domain as Standard
        MDR.Status.objects.create(
            concept=value_domain,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2017, 1, 1)
        )
        # Retire it later
        MDR.Status.objects.create(
            concept=value_domain,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2018, 1, 1)
        )

        # Assert that Retired is displayed
        query_string = "?ra=" + str(self.ra.id) + '&status=' + str(MDR.STATES.standard)
        response = self.client.get(reverse('aristotle:data_element_components_tool') + query_string)

        self.assertContainsHtml(response, 'Retired')

