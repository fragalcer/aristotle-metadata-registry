from django.test import TestCase, tag
from django.contrib.auth import get_user_model
from django.urls import reverse

import datetime
from unittest import skip

from aristotle_mdr import models
import aristotle_mdr.contrib.validators.models as vmodels
import aristotle_mdr.tests.utils as utils

from aristotle_bg_workers.tasks import register_items


# This is for testing permissions around RA management.

class RACreationTests(utils.LoggedInViewPages, TestCase):
    def test_anon_cannot_create(self):
        self.logout()
        response = self.client.get(reverse('aristotle:registrationauthority_create'))
        self.assertRedirects(response,
                             reverse("friendly_login", ) + "?next=" +
                             reverse('aristotle:registrationauthority_create')
                             )

    def test_viewer_cannot_create(self):
        self.login_viewer()

        response = self.client.get(reverse('aristotle:registrationauthority_create'))
        self.assertEqual(response.status_code, 403)

        before_count = models.RegistrationAuthority.objects.count()
        response = self.client.post(
            reverse('aristotle:registrationauthority_create'),
            {
                'name': "My cool team",
                'definition': "This team rocks!",
                "stewardship_organisation": self.steward_org_1.uuid
            }
        )
        self.assertEqual(response.status_code, 403)
        after_count = models.RegistrationAuthority.objects.count()
        self.assertEqual(after_count, before_count)

    def test_manager_cannot_create(self):
        self.login_manager()

        response = self.client.get(reverse('aristotle:registrationauthority_create'))
        self.assertEqual(response.status_code, 403)

        before_count = models.RegistrationAuthority.objects.count()
        response = self.client.post(
            reverse('aristotle:registrationauthority_create'),
            {
                'name': "My cool team",
                'definition': "This team rocks!",
                "stewardship_organisation": self.steward_org_1.uuid
            }
        )
        self.assertEqual(response.status_code, 403)
        after_count = models.RegistrationAuthority.objects.count()
        self.assertEqual(after_count, before_count)

    def test_registry_owner_can_create(self):
        self.login_superuser()

        response = self.client.get(reverse('aristotle:registrationauthority_create'))
        self.assertEqual(response.status_code, 200)

        before_count = models.RegistrationAuthority.objects.count()
        response = self.client.post(
            reverse('aristotle:registrationauthority_create'),
            {
                'name': "My cool registrar",
                'definition': "This RA rocks!",
                "stewardship_organisation": self.steward_org_1.uuid
            },
            follow=True
        )

        self.assertTrue(response.redirect_chain[0][1] == 302)

        self.assertEqual(response.status_code, 200)
        after_count = models.RegistrationAuthority.objects.count()
        self.assertEqual(after_count, before_count + 1)

        new_ra = response.context['item']

        self.assertEqual(new_ra.name, "My cool registrar")
        self.assertEqual(new_ra.definition, "This RA rocks!")


class RAUpdateTests(utils.AristotleTestUtils, TestCase):

    def setUp(self):
        super().setUp()
        self.test_ra = models.RegistrationAuthority.objects.create(
            name='Test Registration Authority',
            definition='Just for testing',
            stewardship_organisation=self.steward_org_1
        )

    def test_anon_cannot_update(self):
        self.logout()
        response = self.client.get(reverse('aristotle:registrationauthority_create'))
        self.assertRedirects(response,
                             reverse("friendly_login", ) + "?next=" +
                             reverse('aristotle:registrationauthority_create')
                             )

    def test_viewer_cannot_update(self):
        self.login_viewer()

        my_ra = models.RegistrationAuthority.objects.create(name="My new RA", definition="",
                                                            stewardship_organisation=self.steward_org_1)

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]))
        self.assertEqual(response.status_code, 403)

        data = {
            'name': "My cool registrar",
            'definition': "This RA rocks!",
            "stewardship_organisation": self.steward_org_1.uuid
        }

        response = self.client.post(
            reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]),
            data
        )
        self.assertEqual(response.status_code, 403)
        my_ra = models.RegistrationAuthority.objects.get(pk=my_ra.pk)

        self.assertNotEqual(my_ra.name, "My cool registrar")
        self.assertNotEqual(my_ra.definition, "This RA rocks!")

    def test_registry_owner_can_edit(self):
        self.login_superuser()

        my_ra = models.RegistrationAuthority.objects.create(name="My new RA", definition="",
                                                            stewardship_organisation=self.steward_org_1)

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]))
        self.assertEqual(response.status_code, 200)

        data = response.context['form'].initial
        data.update({
            'name': "My cool registrar",
            'definition': "This RA rocks!"
        })

        response = self.client.post(
            reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]),
            data
        )
        self.assertEqual(response.status_code, 302)
        my_ra = models.RegistrationAuthority.objects.get(pk=my_ra.pk)

        self.assertEqual(my_ra.name, "My cool registrar")
        self.assertEqual(my_ra.definition, "This RA rocks!")

    def test_ramanager_can_edit(self):
        self.login_ramanager()

        my_ra = models.RegistrationAuthority.objects.create(name="My new RA", definition="",
                                                            stewardship_organisation=self.steward_org_1)

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]))
        self.assertEqual(response.status_code, 403)

        my_ra.managers.add(self.ramanager)
        my_ra = models.RegistrationAuthority.objects.get(pk=my_ra.pk)
        self.assertTrue(self.ramanager in my_ra.managers.all())

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]))
        self.assertEqual(response.status_code, 200)

        data = response.context['form'].initial
        data.update({
            'name': "My cool registrar",
            'definition': "This RA rocks!",
        })

        response = self.client.post(
            reverse('aristotle:registrationauthority_edit', args=[my_ra.pk]),
            data
        )
        self.assertEqual(response.status_code, 302)
        my_ra = models.RegistrationAuthority.objects.get(pk=my_ra.pk)

        self.assertEqual(my_ra.name, "My cool registrar")
        self.assertEqual(my_ra.definition, "This RA rocks!")

    def test_can_change_ra_states(self):
        """Test that an RA can change their locked and public levels"""
        self.assertEqual(self.test_ra.locked_state, models.STATES.candidate)
        self.assertEqual(self.test_ra.public_state, models.STATES.recorded)

        self.test_ra.managers.add(self.ramanager)
        self.login_ramanager()

        response = self.reverse_post(
            'aristotle:registrationauthority_edit_states',
            {
                'locked_state': models.STATES.qualified,
                'public_state': models.STATES.standard
            },
            reverse_args=[self.test_ra.pk]
        )
        self.assertEqual(response.status_code, 302)

        self.test_ra.refresh_from_db()
        self.assertEqual(self.test_ra.locked_state, models.STATES.qualified)
        self.assertEqual(self.test_ra.public_state, models.STATES.standard)

    def test_cannot_set_locked_below_public(self):
        """Test that an RA can't put locked below public"""
        self.test_ra.managers.add(self.ramanager)
        self.login_ramanager()

        response = self.reverse_post(
            'aristotle:registrationauthority_edit_states',
            {
                'locked_state': models.STATES.preferred,
                'public_state': models.STATES.standard
            },
            reverse_args=[self.test_ra.pk]
        )
        self.assertEqual(response.status_code, 200)

        form = response.context['form']
        nfe = form.non_field_errors()
        # Make sure form is invalid
        self.assertFalse(form.is_valid())
        # Make sure there are non form errors that are rendererd
        self.assertTrue(len(nfe) > 0)
        self.assertContains(response, nfe[0])


class RAListTests(utils.LoggedInViewPages, TestCase):
    def test_anon_cannot_create(self):
        self.logout()
        response = self.client.get(reverse('aristotle:registrationauthority_list'))
        self.assertRedirects(response,
                             reverse("friendly_login", ) + "?next=" +
                             reverse('aristotle:registrationauthority_list')
                             )

    def test_viewer_cannot_list(self):
        self.login_viewer()

        response = self.client.get(reverse('aristotle:registrationauthority_list'))
        self.assertEqual(response.status_code, 403)

    def test_ramanager_cannot_list(self):
        self.login_ramanager()

        response = self.client.get(reverse('aristotle:registrationauthority_list'))
        self.assertEqual(response.status_code, 403)

    def test_registry_owner_can_list(self):
        self.login_superuser()

        response = self.client.get(reverse('aristotle:registrationauthority_list'))
        self.assertEqual(response.status_code, 200)

    @tag('registrar_tools')
    def test_viewer_cannot_tools_list(self):
        self.login_viewer()

        response = self.client.get(reverse('aristotle_mdr:userRegistrarTools'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 0)

    @tag('registrar_tools')
    def test_viewer_can_tools_list(self):
        self.login_registrar()

        response = self.client.get(reverse('aristotle_mdr:userRegistrarTools'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 1)

    @tag('registrar_tools')
    def test_manager_can_tools_list(self):
        self.login_ramanager()

        response = self.client.get(reverse('aristotle_mdr:userRegistrarTools'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page'].object_list), 1)


class RAManageTests(utils.LoggedInViewPages, TestCase):
    def setUp(self):
        super().setUp()
        self.empty_ra = models.RegistrationAuthority.objects.create(
            name="Test RA", definition="No one is a member of this",
            stewardship_organisation=self.steward_org_1
        )

    def test_anon_cannot_edit(self):
        self.logout()
        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[self.ra.pk]))
        self.assertRedirects(response,
                             reverse("friendly_login", ) + "?next=" +
                             reverse('aristotle:registrationauthority_edit', args=[self.ra.pk])
                             )

    def test_viewer_cannot_edit(self):
        self.login_viewer()

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[self.ra.pk]))
        self.assertEqual(response.status_code, 403)

    def test_ramanager_can_edit(self):
        self.login_ramanager()

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[self.ra.pk]))
        self.assertEqual(response.status_code, 200)

        self.ra.managers.remove(self.ramanager)
        self.ra = models.RegistrationAuthority.objects.get(pk=self.ra.pk)
        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[self.ra.pk]))
        self.assertEqual(response.status_code, 403)

    def test_registry_owner_can_edit(self):
        self.login_superuser()

        response = self.client.get(reverse('aristotle:registrationauthority_edit', args=[self.ra.pk]))
        self.assertEqual(response.status_code, 200)

    def test_viewer_cannot_view_add_change_or_remove_users(self):
        self.login_viewer()
        response = self.client.get(reverse('aristotle:registrationauthority_members', args=[self.ra.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:registrationauthority_add_user', args=[self.ra.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            reverse('aristotle:registrationauthority_change_user_roles', args=[self.ra.id, self.newuser.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            reverse('aristotle:registrationauthority_member_remove', args=[self.ra.id, self.newuser.pk]))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_add_or_change_users(self):
        self.login_ramanager()
        self.assertTrue(self.newuser in list(get_user_model().objects.all()))

        response = self.client.get(reverse('aristotle:registrationauthority_add_user', args=[self.empty_ra.id]))
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('aristotle:registrationauthority_add_user', args=[self.ra.id]))
        self.assertEqual(response.status_code, 200)

        self.assertTrue(self.newuser.id in [u[0] for u in response.context['form'].fields['user'].choices])

        self.assertListEqual(list(self.newuser.profile.workgroups.all()), [])
        response = self.client.post(
            reverse('aristotle:registrationauthority_add_user', args=[self.empty_ra.id]),
            {
                'roles': ['registrar'],
                'user': self.newuser.pk
            }
        )
        self.assertEqual(response.status_code, 403)
        self.assertListEqual(list(self.newuser.profile.workgroups.all()), [])

        response = self.client.post(
            reverse('aristotle:registrationauthority_add_user', args=[self.ra.id]),
            {
                'roles': ['registrar'],
                'user': self.newuser.pk
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.newuser in self.ra.registrars.all())
        self.assertTrue(self.newuser in self.ra.members.all())
        self.assertListEqual(list(self.newuser.profile.registrarAuthorities.all()), [self.ra])

        response = self.client.get(
            reverse('aristotle:registrationauthority_change_user_roles', args=[self.ra.id, self.newuser.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse('aristotle:registrationauthority_change_user_roles', args=[self.ra.id, self.newuser.pk]),
            {'roles': ['manager']}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.newuser in self.ra.registrars.all())
        self.assertTrue(self.newuser in self.ra.managers.all())
        response = self.client.post(
            reverse('aristotle:registrationauthority_change_user_roles', args=[self.ra.id, self.newuser.pk]),
            {'roles': []}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.newuser in self.ra.registrars.all())
        self.assertFalse(self.newuser in self.ra.managers.all())
        self.assertFalse(self.newuser in self.ra.members.all())

    def test_manager_can_remove_users(self):
        self.login_ramanager()
        self.assertTrue(self.newuser in list(get_user_model().objects.all()))

        response = self.client.post(
            reverse('aristotle:registrationauthority_add_user', args=[self.ra.id]),
            {
                'roles': ['registrar', 'manager'],
                'user': self.newuser.pk
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.newuser in self.ra.members.all())
        self.assertTrue(self.newuser in self.ra.registrars.all())
        self.assertTrue(self.newuser in self.ra.managers.all())
        self.assertListEqual(list(self.newuser.profile.registrarAuthorities.all()), [self.ra])

        response = self.client.post(
            reverse('aristotle:registrationauthority_member_remove', args=[self.ra.id, self.newuser.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.newuser in self.ra.registrars.all())
        self.assertFalse(self.newuser in self.ra.managers.all())

        response = self.client.get(
            reverse('aristotle:registrationauthority_member_remove', args=[self.ra.id, self.newuser.pk]),
        )
        self.assertEqual(response.status_code, 404)

    def test_get_existing_ra_rules(self):
        self.login_ramanager()
        rules = vmodels.RAValidationRules.objects.create(
            registration_authority=self.ra
        )
        response = self.client.get(
            reverse('aristotle:registrationauthority_rules', args=[self.ra.id])
        )
        self.assertEqual(response.context['rules'], rules)
        self.assertEqual(response.status_code, 200)


class RegisterTaskTests(utils.AristotleTestUtils, TestCase):
    """Tests the register_items task"""

    def setUp(self):
        super().setUp()
        self.oc = models.ObjectClass.objects.create(
            name='Animal',
            definition='An animal',
            workgroup=self.wg1
        )
        self.prop = models.Property.objects.create(
            name='Speed',
            definition='Fastness',
            workgroup=self.wg1
        )
        self.dec = models.DataElementConcept.objects.create(
            name='Animal - Speed',
            definition='An animals speed',
            objectClass=self.oc,
            property=self.prop,
            workgroup=self.wg1
        )

    def check_registered_std(self, item):
        status = item.statuses.order_by('-created').first()
        self.assertIsNotNone(status)
        self.assertEqual(status.registrationAuthority, self.ra)
        self.assertEqual(status.state, models.STATES.standard)

    def test_registration(self):
        ids = [self.oc.id, self.prop.id, self.dec.id]

        register_items(
            ids,
            False,
            models.STATES.standard,
            self.ra.id,
            self.su.id,
            '',
            (2001, 1, 1)
        )

        self.check_registered_std(self.oc)
        self.check_registered_std(self.prop)
        self.check_registered_std(self.dec)


class TestDataDictionary(utils.AristotleTestUtils, TestCase):
    def check_registered_std(self, item):
        status = item.statuses.order_by('-created').first()
        self.assertIsNotNone(status)
        self.assertEqual(status.registrationAuthority, self.ra)
        self.assertEqual(status.state, models.STATES.standard)

    def setUp(self):
        super().setUp()

        self.second_ra = models.RegistrationAuthority.objects.create(name="Health",
                                                                     definition="Health Registration Auth",
                                                                     stewardship_organisation=self.steward_org_1)
        self.oc = models.ObjectClass.objects.create(
            name='Animal',
            definition='An animal',
            workgroup=self.wg1,
        )

    def test_overlapping_registrations_with_different_ras(self):
        # Register the concept with the first RA, registered from 2018 to perpetuity
        self.ra.register(self.oc, models.STATES.standard, self.su,
                         effective_date=datetime.date(2018, 1, 1),
                         until_date=datetime.date(2019, 1, 1)
                         )

        # Register the concept again with a different RA, registered from 2019 to perpetuity
        self.second_ra.register(self.oc,
                                models.STATES.standard,
                                self.su,
                                effective_date=datetime.date(2019, 1, 1))

        # Go to the data dictionary page for the second Registration Authority
        self.login_superuser()
        response = self.client.get(
            reverse('aristotle:registrationauthority_data_dictionary', args=[self.second_ra.id]) +
            '?registration_date=2018-6-6&status=5'
        )
        self.assertEqual(response.status_code, 200)
        # Check that there is nothing in the queryset
        self.assertFalse(response.context['object_list'].exists())

    def test_data_dictionary_filters_status(self):
        # Register the concept, status is 5
        self.ra.register(self.oc, models.STATES.standard, self.su,
                         effective_date=datetime.date(2018, 1, 1))

        self.check_registered_std(self.oc)

        # Go to the data dictionary page for the first Registration Authority
        self.login_superuser()
        response = self.client.get(
            reverse('aristotle:registrationauthority_data_dictionary', args=[self.ra.id]) +
            '?registration_date=2018-6-6&status=4&concept_type=23'
        )
        self.assertEqual(response.status_code, 200)
        # Check that there is nothing in the queryset
        self.assertFalse(response.context['object_list'].exists())

    def test_data_dictionary_filters_date(self):
        # Register the concept, status is 5
        self.ra.register(self.oc, models.STATES.standard, self.su,
                         effective_date=datetime.date(2018, 1, 1))

        self.check_registered_std(self.oc)

        self.login_superuser()

        response = self.client.get(
            reverse('aristotle:registrationauthority_data_dictionary', args=[self.ra.id]) +
            '?registration_date=2017-1-1&status=5'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['object_list'].exists())

    def test_data_dictionary_displays_closest_registration_date(self):
        # Register the concept twice with the same status
        self.ra.register(self.oc, models.STATES.standard, self.su,
                         effective_date=datetime.date(2018, 1, 1))
        self.ra.register(self.oc, models.STATES.standard, self.su,
                         effective_date=datetime.date(2016, 1, 1))

        self.check_registered_std(self.oc)

        self.login_superuser()

        response = self.client.get(
            reverse('aristotle:registrationauthority_data_dictionary', args=[self.ra.id]) +
            '?registration_date=2018-1-2&status=5'
        )
        self.assertEqual(response.status_code, 200)
        # Check that the date rendered is closest to queried date
        for concept, status in response.context['concepts'].items():
            self.assertEqual(status.effective_date, datetime.date(2018, 1, 1))

    def test_data_dictionary_filters_concept_type(self):
        self.ra.register(self.oc.concept, models.STATES.standard, self.su,
                         effective_date=datetime.date(2018, 1, 1))

        self.check_registered_std(self.oc)
        self.oc.refresh_from_db()
        self.assertIsNotNone(self.oc._type)

        self.login_superuser()

        response = self.client.get(reverse('aristotle:registrationauthority_data_dictionary', args=[self.ra.id]) +
                                   '?registration_date=2019-1-2&status=5&concept_type={}'.format(self.oc.item_type.id))

        self.assertTrue(response.context['object_list'].exists())
