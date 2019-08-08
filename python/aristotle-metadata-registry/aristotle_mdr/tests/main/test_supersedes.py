from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.urls import reverse
from django.utils import timezone

import aristotle_mdr.models as models
from aristotle_mdr import perms
import aristotle_mdr.tests.utils as utils
from aristotle_mdr.utils import url_slugify_concept


class SupersededProperty(TestCase):
    def setUp(self):
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")
        self.wg = models.Workgroup.objects.create(name="Test WG", stewardship_organisation=self.steward_org_1)
        self.item1 = models.ObjectClass.objects.create(name="OC1", workgroup=self.wg)
        self.item2 = models.ObjectClass.objects.create(name="OC2", workgroup=self.wg)
        self.ra = models.RegistrationAuthority.objects.create(name="Test RA", stewardship_organisation=self.steward_org_1)

    def test_is_supersede_property(self):
        self.assertFalse(self.item1.is_superseded)
        self.item1.superseded_by = self.item2
        models.SupersedeRelationship.objects.create(
            older_item=self.item1,
            newer_item=self.item2,
            registration_authority=self.ra
        )
        models.Status.objects.create(
            state=models.STATES.superseded,
            registrationAuthority=self.ra,
            concept=self.item1,
            effective_date=timezone.now()
        )
        self.item1.save()
        self.assertTrue(self.item1.is_superseded)

        s = models.Status.objects.create(
            concept=self.item1,
            registrationAuthority=self.ra,
            effective_date=timezone.now(),
            state=self.ra.public_state
        )
        # self.item1=models.ObjectClass.objects.get(id=self.item1.id)

        self.assertFalse(self.item1.is_superseded)
        s.state = models.STATES.superseded
        s.save()
        self.assertTrue(self.item1.is_superseded)


class SupersedePage(utils.AristotleTestUtils, TestCase):
    def setUp(self):
        super().setUp()

        # There would be too many tests to test every item type against every other
        # But they all have identical logic, so one test should suffice
        self.item1 = models.ObjectClass.objects.create(name="OC1", workgroup=self.wg1)
        self.item2 = models.ObjectClass.objects.create(name="OC2", workgroup=self.wg1)
        self.item3 = models.ObjectClass.objects.create(name="OC3", workgroup=self.wg2)
        self.item4 = models.Property.objects.create(name="Prop4", workgroup=self.wg1)

    def make_standard(self, item):
        self.ra.register(
            item,
            models.STATES.standard,
            self.su
        )

    @tag('unit_test', 'supersede')
    def test_supersede_querysets(self):
        # We just want to check that the superseded relationships can
        # now use the visible queryset query
        self.item1.superseded_by_items.visible(self.registrar).all()
        self.item2.superseded_items.visible(self.registrar).all()

    @tag('unit_test', 'supersede')
    def test_supersede_form(self):
        from aristotle_mdr.forms.actions import SupersedeAdminForm
        self.ra.register(
            self.item1,
            models.STATES.standard,
            self.su
        )
        self.ra.register(
            self.item2,
            models.STATES.standard,
            self.su
        )

        form_data = {
            'older_item': self.item2,
            'registration_authority': self.ra,
        }

        form = SupersedeAdminForm(data=form_data, item=self.item1, user=self.registrar)
        self.assertTrue(form.is_valid())

        form = SupersedeAdminForm(data=form_data, item=self.item1, user=self.su)
        self.assertTrue(form.is_valid())

        form = SupersedeAdminForm(data=form_data, item=self.item1, user=self.editor)
        self.assertFalse(form.is_valid())

        ra2 = models.RegistrationAuthority.objects.create(name="Test RA", definition="My WG", stewardship_organisation=self.steward_org_1)
        new_registrar = get_user_model().objects.create_user('newbie@example.com', 'new registrar')
        ra2.registrars.add(self.registrar)

        self.assertTrue(self.item1.can_view(new_registrar))
        self.assertTrue(self.item2.can_view(new_registrar))
        form = SupersedeAdminForm(data=form_data, item=self.item1, user=new_registrar)
        self.assertFalse(form.is_valid())

    @tag('integration_test', 'supersede')
    def test_supersede(self):
        self.logout()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertRedirects(
            response,
            reverse("friendly_login") + "?next=" + reverse('aristotle:supersede', args=[self.item1.id])
        )

        self.ra.register(
            self.item1,
            models.STATES.superseded,
            self.su
        )
        self.ra.register(
            self.item2,
            models.STATES.standard,
            self.su
        )

        # Make sure we can't access the page as an editor
        self.login_editor()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertEqual(response.status_code, 403)

        # Make sure we can access the page as a registar
        self.login_registrar()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.item1.superseded_items_relation_set.count(), 0)

        management_form = utils.MockManagementForm(
            prefix="superseded_items_relation_set",
        )
        management_form.add_form({
            'older_item': self.item1.id,
            'registration_authority': self.ra.pk,
            'message': '',
            'date_effective': '',
        })

        # An item cannot supersede itself, so it did not save and was served the form again.
        response = self.client.post(
            reverse('aristotle:supersede', args=[self.item1.id]),
            management_form.as_dict()
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context['formset'].errors[0]['older_item']), 1)
        self.assertTrue('older_item' in response.context['formset'].errors[0].keys())
        self.assertTrue(
            "may not supersede itself" in response.context['formset'].errors[0]['older_item'][0]
        )
        self.assertEqual(
            models.ObjectClass.objects.get(id=self.item1.id).superseded_items_relation_set.count(), 0
        )

        management_form = utils.MockManagementForm(
            prefix="superseded_items_relation_set",
        )
        management_form.add_form({
            'older_item': self.item2.id,
            'registration_authority': self.ra.pk,
            'message': '',
            'date_effective': '',
        })

        # Item 2 can supersede item 1, so this saved and redirected properly.
        response = self.client.post(
            reverse('aristotle:supersede', args=[self.item1.id]),
            management_form.as_dict()
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            self.item2 in models.ObjectClass.objects.get(id=self.item1.id).superseded_items.all()
        )

        management_form = utils.MockManagementForm(
            prefix="superseded_items_relation_set",
        )
        management_form.add_form({
            'older_item': self.item3.id,
            'registration_authority': self.ra.pk,
            'message': '',
            'date_effective': '',
        })

        response = self.client.post(
            reverse('aristotle:supersede', args=[self.item1.id]),
            management_form.as_dict()
        )
        # Item 3 is a different workgroup, and the editor cannot see it, so
        # cannot supersede, so it did not save and was served the form again.
        self.assertFalse(self.item3.can_view(self.registrar))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.item3 not in models.ObjectClass.objects.get(
            id=self.item1.id
        ).superseded_items.all()
        )

        management_form = utils.MockManagementForm(
            prefix="superseded_items_relation_set",
        )
        management_form.add_form({
            'older_item': self.item3.id,
            'registration_authority': self.ra.pk,
            'message': '',
            'date_effective': '',
        })

        response = self.client.post(
            reverse('aristotle:supersede', args=[self.item1.id]),
            management_form.as_dict()
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            self.item4 not in models.ObjectClass.objects.get(id=self.item1.id).superseded_items.all()
        )

    @tag('integration_test', 'supersede')
    def test_viewer_cannot_view_supersede_page(self):
        self.login_viewer()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:supersede', args=[self.item2.id]))
        self.assertEqual(response.status_code, 403)

    @tag('integration_test', 'supersede')
    def test_editor_cannot_view_supersede_page(self):
        self.login_editor()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:supersede', args=[self.item2.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:supersede', args=[self.item3.id]))
        self.assertEqual(response.status_code, 403)

    @tag('integration_test', 'supersede')
    def test_registrar_can_view_supersede_page(self):
        self.ra.register(
            self.item1,
            models.STATES.standard,
            self.su
        )
        self.ra.register(
            self.item3,
            models.STATES.standard,
            self.su
        )
        self.login_registrar()
        response = self.client.get(reverse('aristotle:supersede', args=[self.item1.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:supersede', args=[self.item2.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('aristotle:supersede', args=[self.item3.id]))
        self.assertEqual(response.status_code, 200)

    def test_propose_supersede(self):
        self.login_editor()

        self.assertTrue(perms.user_can_edit(self.editor, self.item1))

        # Get formset postdata for single supersedes
        postdata = self.get_formset_postdata(
            [{
                'older_item': self.item2.id,
                'registration_authority': self.ra.id,
                'message': '',
                'date_effective': ''
            }],
            prefix='superseded_items_relation_set'
        )

        response = self.reverse_post(
            'aristotle:proposed_supersede',
            postdata,
            reverse_args=[self.item1.id],
        )

        self.assertRedirects(response, url_slugify_concept(self.item1))
        self.assertEqual(self.item1.superseded_items_relation_set.count(), 1)
        ss = self.item1.superseded_items_relation_set.first()
        self.assertTrue(ss.proposed)

    def test_edit_existing_proposed_supersedes(self):
        # Make some supersedes relations
        ss = models.SupersedeRelationship.objects.create(
            proposed=False,
            newer_item=self.item1,
            older_item=self.item2,
            registration_authority=self.ra,
        )
        ssp = models.SupersedeRelationship.objects.create(
            proposed=True,
            newer_item=self.item1,
            older_item=self.item3,
            registration_authority=self.ra,
        )

        # Make registrar a manager so they can edit the item
        self.wg1.giveRoleToUser('manager', self.registrar)
        self.login_editor()

        response = self.reverse_get(
            'aristotle:proposed_supersede',
            reverse_args=[self.item1.id]
        )
        self.assertEqual(response.status_code, 200)

        formset = response.context['formset']
        self.assertEqual(len(formset), 1)
        self.assertEqual(formset[0].initial['older_item'], self.item3.id)

    def test_edit_existing_all_supersedes(self):
        # Register items so registrar can use them
        self.make_standard(self.item1)
        self.make_standard(self.item2)
        # Make some supersedes relations
        ss = models.SupersedeRelationship.objects.create(
            proposed=False,
            newer_item=self.item1,
            older_item=self.item2,
            registration_authority=self.ra,
        )
        ssp = models.SupersedeRelationship.objects.create(
            proposed=True,
            newer_item=self.item1,
            older_item=self.item3,
            registration_authority=self.ra,
        )

        self.login_registrar()
        response = self.reverse_get(
            'aristotle:supersede',
            reverse_args=[self.item1.id]
        )
        self.assertEqual(response.status_code, 200)

        formset = response.context['formset']
        self.assertEqual(len(formset), 2)
        self.assertEqual(formset[0].initial['older_item'], self.item2.id)
        self.assertEqual(formset[1].initial['older_item'], self.item3.id)

    def test_proposed_supersedes_show_in_edit_form(self):
        # Register items so registrar can use them
        self.make_standard(self.item1)
        self.make_standard(self.item2)
        # Make proposed supersede
        ss = models.SupersedeRelationship.objects.create(
            proposed=True,
            older_item=self.item1,
            newer_item=self.item2,
            registration_authority=self.ra,
        )

        self.login_registrar()
        response = self.reverse_get(
            'aristotle:supersede',
            reverse_args=[self.item2.id]
        )
        self.assertEqual(response.status_code, 200)

        formset = response.context['formset']
        self.assertEqual(len(formset), 1)

    def test_approve_supersede_by_editing(self):
        # Register items so registrar can use them
        self.make_standard(self.item1)
        self.make_standard(self.item2)
        # Make proposed supersede
        ss = models.SupersedeRelationship.objects.create(
            proposed=True,
            older_item=self.item2,
            newer_item=self.item1,
            registration_authority=self.ra,
        )

        # Get formset postdata for single supersedes
        postdata = self.get_formset_postdata(
            [{
                'id': ss.id,
                'older_item': ss.older_item.id,
                'registration_authority': ss.registration_authority.id,
                # Dont submit proposed (it's a checkbox)
                'message': ss.message,
                'date_effective': ''
            }],
            prefix='superseded_items_relation_set',
            initialforms=1
        )

        self.login_registrar()
        response = self.reverse_post(
            'aristotle:supersede',
            postdata,
            reverse_args=[self.item1.id],
        )
        self.assertRedirects(response, url_slugify_concept(self.item1))

        self.assertEqual(self.item1.superseded_items_relation_set.all().count(), 1)

        ss.refresh_from_db()
        self.assertFalse(ss.proposed)
