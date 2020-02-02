from unittest import skip

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.test import TestCase, tag

from aristotle_mdr.contrib.links import models, perms
from aristotle_mdr.models import ObjectClass, STATES, Status
from aristotle_mdr.tests import utils
from aristotle_mdr.utils import url_slugify_concept

from aristotle_mdr.tests.main.test_admin_pages import AdminPageForConcept
from aristotle_mdr.tests.main.test_html_pages import LoggedInViewConceptPages
from aristotle_mdr.tests.main.test_wizards import ConceptWizardPage

import datetime


def setUpModule():
    from django.core.management import call_command
    call_command('load_aristotle_help', verbosity=0)


class RelationViewPage(LoggedInViewConceptPages, TestCase):
    url_name = 'relation'
    itemType = models.Relation

    def setUp(self):
        super().setUp()

        for i in range(4):
            models.RelationRole.objects.create(
                name="test name",
                definition="test definition",
                relation=self.item1,
                ordinal=i,
                multiplicity=3,
            )

    def test_weak_editing_in_advanced_editor_dynamic(self, updating_field=None, default_fields={}):
        super().test_weak_editing_in_advanced_editor_dynamic(updating_field='definition')


class RelationAdminPage(AdminPageForConcept, TestCase):
    itemType = models.Relation
    form_defaults = {
        'relationrole_set-TOTAL_FORMS': 0,
        'relationrole_set-INITIAL_FORMS': 0,
        'relationrole_set-MAX_NUM_FORMS': 1,
    }


class RelationCreationWizard(ConceptWizardPage, TestCase):
    model = models.Relation

    @tag('edit_formsets')
    def test_weak_editor_during_create(self):
        self.login_editor()

        item_name = 'My New Relation'
        step_1_data = {
            self.wizard_form_name + '-current_step': 'initial',
            'initial-name': item_name,
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'results')

        step_2_data = {
            self.wizard_form_name + '-current_step': 'results',
            'initial-name': item_name,
            'results-name': item_name,
            'results-definition': "Test Definition",
        }
        step_2_data.update(self.get_formset_postdata([], 'slots'))

        step_2_data.update(self.get_formset_postdata([], 'org_records'))

        role_formset_data = [
            {'name': 'parent', 'definition': 'ok', 'multiplicity': 1, 'ORDER': 0},
            {'name': 'child', 'definition': 'good', 'multiplicity': 1, 'ORDER': 1}
        ]

        step_2_data.update(self.get_formset_postdata(role_formset_data, 'roles'))

        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(self.model.objects.filter(name=item_name).exists())
        self.assertEqual(self.model.objects.filter(name=item_name).count(), 1)
        item = self.model.objects.filter(name=item_name).first()
        self.assertRedirects(response, url_slugify_concept(item))

        roles = item.relationrole_set.all().order_by('ordinal')

        self.assertEqual(roles[0].ordinal, 0)
        self.assertEqual(roles[0].name, 'parent')
        self.assertEqual(roles[0].definition, 'ok')
        self.assertEqual(roles[0].multiplicity, 1)

        self.assertEqual(roles[1].ordinal, 1)
        self.assertEqual(roles[1].name, 'child')
        self.assertEqual(roles[1].definition, 'good')
        self.assertEqual(roles[1].multiplicity, 1)


class LinkTestBase(utils.AristotleTestUtils):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.item1 = ObjectClass.objects.create(
            name="Test Item 1 (visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg1,
        )
        self.item2 = ObjectClass.objects.create(
            name="Test Item 2 (NOT visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg2,
        )
        self.item3 = ObjectClass.objects.create(
            name="Test Item 3 (visible to tested viewers)",
            definition="my definition",
            workgroup=self.wg1,
        )
        self.item4 = ObjectClass.objects.create(
            name="Test Item 4 (visible to only superusers)",
            definition="my definition",
        )

        self.relation = models.Relation.objects.create(name="test_relation", definition="Used for testing")
        self.relation_role1 = models.RelationRole.objects.create(
            name="part1", definition="first role", multiplicity=1,
            ordinal=1,
            relation=self.relation
        )
        self.relation_role2 = models.RelationRole.objects.create(
            name="part2", definition="second role", multiplicity=1,
            ordinal=2,
            relation=self.relation
        )
        self.role1key = 'role_{}'.format(self.relation_role1.pk)
        self.role2key = 'role_{}'.format(self.relation_role2.pk)

        self.link1 = models.Link.objects.create(
            relation=self.relation,
            root_item=self.item1
        )
        self.link1_end1 = self.link1.add_link_end(
            role=self.relation_role1,
            concept=self.item1
        )
        self.link1_end2 = self.link1.add_link_end(
            role=self.relation_role2,
            concept=self.item2
        )

        self.link2 = models.Link.objects.create(
            relation=self.relation,
            root_item=self.item2
        )
        self.link2_end1 = self.link2.add_link_end(
            role=self.relation_role1,
            concept=self.item2
        )
        self.link2_end2 = self.link2.add_link_end(
            role=self.relation_role2,
            concept=self.item4
        )

        self.blank_relation = models.Relation.objects.create(
            name='Blank Relation',
            definition='Super blank'
        )


class TestLinkPages(LinkTestBase, TestCase):

    def register_relation(self, relation=None):

        if not relation:
            relation = self.relation

        self.ra.register(
            item=relation,
            state=STATES.standard,
            user=self.su
        )

    def test_superuser_can_view_edit_links(self):
        self.login_superuser()
        response = self.client.get(self.item1.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.relation.name)
        self.assertContains(response, "Edit link")
        self.assertContains(response, reverse('aristotle_mdr_links:edit_link', args=[self.link1.pk]))

        response = self.client.get(self.item2.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.relation.name)
        self.assertContains(response, "Edit link")
        self.assertContains(response, reverse('aristotle_mdr_links:edit_link', args=[self.link2.pk]))

    def test_anon_user_cannot_view_edit_links(self):
        see_also = models.Relation.objects.create(name="See Also", definition="See Also")
        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        # Root object class
        root_object_class = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        # Make the main item publicly accessible
        Status.objects.create(
            concept=root_object_class,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=STATES.standard,
        )
        to_object_class = ObjectClass.objects.create(
            name="To Object CLass",
            definition="A definition",
            workgroup=self.wg1,
        )
        Status.objects.create(
            concept=to_object_class,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=STATES.standard
        )

        link = models.Link.objects.create(
            relation=see_also,
            root_item=root_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=root_object_class
        )
        self.logout()
        response = self.client.get(root_object_class.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, see_also)
        self.assertNotContains(response, "Edit link")
        self.assertNotContains(response, reverse('aristotle_mdr_links:edit_link', args=[link.pk]))

    def test_editor_user_can_view_edit_links(self):
        """Test that an editor can view editor links for items they have permission to see"""
        see_also = models.Relation.objects.create(name="Relation",
                                                  definition="Not really necessary",
                                                  workgroup=self.wg1)

        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        root_object_class = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        to_object_class = ObjectClass.objects.create(
            name="To Object CLass",
            definition="A definition",
            workgroup=self.wg1,
        )
        link = models.Link.objects.create(
            relation=see_also,
            root_item=root_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=root_object_class
        )

        self.login_editor()
        response = self.client.get(root_object_class.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, see_also)
        self.assertContains(response, "Edit link")
        self.assertContains(response, reverse('aristotle_mdr_links:edit_link', args=[link.pk]))

    def test_editor_user_can_view_some_edit_link_pages(self):
        self.login_editor()
        response = self.client.get(reverse('aristotle_mdr_links:edit_link', args=[self.link2.pk]))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('aristotle_mdr_links:edit_link', args=[self.link2.pk]),
            {
                "role_%s" % self.relation_role1.pk: [self.item1.pk],
                "role_%s" % self.relation_role2.pk: [self.item3.pk]
            }
        )
        self.assertTrue(self.item1 in self.link1.concepts())
        self.assertTrue(self.item3 not in self.link1.concepts())
        self.assertTrue(self.item2 in self.link1.concepts())
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('aristotle_mdr_links:edit_link', args=[self.link1.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle_mdr_links:edit_link', args=[self.link1.pk]))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse('aristotle_mdr_links:edit_link', args=[self.link1.pk]),
            {
                "role_%s" % self.relation_role1.pk: [self.item1.pk],
                "role_%s" % self.relation_role2.pk: [self.item3.pk]
            }
        )
        self.assertEqual(response.status_code, 302)  # Success!
        self.assertTrue(self.item1 in self.link1.concepts())
        self.assertTrue(self.item2 not in self.link1.concepts())
        self.assertTrue(self.item3 in self.link1.concepts())

    @tag('link_wizard')
    @skip('Skipping for now due to changes in wizard')
    def test_add_link_wizard(self):
        self.wizard_form_name = "add_link_wizard"
        finish_url = reverse("aristotle:item", args=[self.item1.pk])
        self.wizard_url = reverse('aristotle_mdr_links:add_link', args=[self.item1.pk])

        self.register_relation()
        self.item1.linkend_set.all().delete()

        self.assertTrue(self.relation.can_view(self.editor))
        self.assertEqual(self.item1.linkend_set.count(), 0)
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 302)  # Redirects to login

        self.login_editor()

        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)  # OK, lets go!
        self.assertContains(response, "add_link_wizard-current_step")

        step_0_data = {
            self.wizard_form_name + '-current_step': '0',
        }

        response = self.client.post(self.wizard_url, step_0_data)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, '0')
        self.assertTrue('relation' in wizard['form'].errors.keys())

        # must submit a relation
        step_0_data.update({'0-relation': str(self.relation.pk)})
        # success!

        response = self.client.post(self.wizard_url, step_0_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)  # OK, lets go!
        self.assertWizardStep(response, 1)
        self.assertFalse('relation' in wizard['form'].errors.keys())

        self.assertEqual(response.status_code, 200)

        step_1_data = {
            self.wizard_form_name + '-current_step': '1',
            '1-role': self.relation_role1.pk
        }
        response = self.client.post(self.wizard_url, step_1_data)
        self.assertEqual(response.status_code, 200)
        self.assertWizardStep(response, 2)

        step_2_data = {
            self.wizard_form_name + '-current_step': '2'
        }
        for role in self.relation.relationrole_set.all():
            step_2_data.update({'2-role_%s' % role.pk: self.item1.id})

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)  # OK, lets go!

        self.assertEqual(len(wizard['form'].errors.keys()), 0)
        self.assertWizardStep(response, 3)

        step_3_data = {
            self.wizard_form_name + '-current_step': '3'
        }
        response = self.client.post(self.wizard_url, step_3_data)
        self.assertRedirects(response, finish_url, fetch_redirect_response=False)

        self.assertEqual(self.item1.linkend_set.count(), self.relation.relationrole_set.count())

        link = self.relation.link_set.last()
        self.assertEqual(link.root_item, self.item1._concept_ptr)
        self.assertEqual(
            link.linkend_set.get(role=self.relation_role1).concept,
            self.item1._concept_ptr
        )
        self.assertEqual(
            link.linkend_set.get(role=self.relation_role2).concept,
            self.item1._concept_ptr
        )

    def test_add_link_gt1_multiplicity(self):
        self.relation_role1.multiplicity = 3
        self.relation_role1.save()
        self.relation_role2.multiplicity = 3
        self.relation_role2.save()

        self.register_relation()
        self.login_editor()

        wizard_data = [
            {
                'relation': str(self.relation.pk)
            },
            {
                self.role1key: self.item1.pk,
                self.role2key: self.item3.pk
            },
        ]

        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_links:add_link', args=[self.item1.id]),
            'add_link_wizard'
        )
        self.assertEqual(response.status_code, 302)

        link = self.relation.link_set.last()
        self.assertEqual(link.root_item, self.item1._concept_ptr)
        self.assertEqual(
            link.linkend_set.get(role=self.relation_role1).concept,
            self.item1._concept_ptr
        )
        self.assertEqual(
            link.linkend_set.get(role=self.relation_role2).concept,
            self.item3._concept_ptr
        )

    def test_add_roles_to_relation(self):
        """ Test whether adding roles to a relation via the formset is working successfully"""

        self.empty_relation = models.Relation.objects.create(
            name='Blank Relation',
            definition='Super blank',
            submitter=self.editor,
            workgroup=self.wg1
        )

        self.login_editor()

        # Generate the POST data
        postdata = self.get_formset_postdata(
            [{
                'name': "A role",
                'definition': "Something that must be performed",
                'multiplicity': 1,
                'relation': self.empty_relation.pk,
                'ORDER': 0  # Order refers to the ordinality in the db
            }],
            prefix='relationrole_set',
            initialforms=0
        )

        # POST the data to the view
        response = self.reverse_post(
            'aristotle_mdr_links:relation_roles_edit',
            postdata,
            reverse_args=[self.empty_relation.id],
        )

        # Assert that the form was redirected
        self.assertEqual(response.status_code, 302)

        # Check that relational role was created
        roles = self.empty_relation.relationrole_set.all().order_by('ordinal')

        self.assertEqual(roles[0].name, "A role")
        self.assertEqual(roles[0].definition, "Something that must be performed")
        self.assertEqual(roles[0].multiplicity, 1)

    def test_add_link_root_item_set(self):
        self.login_editor()
        response = self.reverse_get(
            'aristotle_mdr_links:add_link',
            reverse_args=[self.item1.id],
            status_code=200
        )

        self.assertEqual(response.context['view'].root_item, self.item1._concept_ptr)

    def test_cant_add_link_on_non_editable_item(self):
        self.login_viewer()
        response = self.reverse_get(
            'aristotle_mdr_links:add_link',
            reverse_args=[self.item1.id],
            status_code=403
        )

    # Used by 2 following tests
    def check_root_item_is_required_as_one_end(self):

        self.register_relation()
        self.login_editor()

        wizard_data = [
            {
                'relation': str(self.relation.pk)
            },
            {
                self.role1key: self.item2.pk,
                self.role2key: self.item3.pk
            }
        ]

        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_links:add_link', args=[self.item1.id]),
            'add_link_wizard'
        )
        self.assertWizardStep(response, 1)

        # Check that the error is actually rendered
        self.assertContains(response, 'Must be one of the attached concepts')

    def test_root_item_is_required_as_one_end(self):
        self.check_root_item_is_required_as_one_end()

    def test_root_item_is_required_gt1_multiplicity(self):
        self.relation_role1.multiplicity = 3
        self.relation_role1.save()
        self.relation_role2.multiplicity = 3
        self.relation_role2.save()

        self.check_root_item_is_required_as_one_end()

    def test_link_viewable_from_root(self):
        """Test that a link is viewable from the root item"""

        see_also = models.Relation.objects.create(name="Relation", definition="Not really necessary")

        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        # Root object class
        root_object_class = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        # Make the main item publicly accessible
        Status.objects.create(
            concept=root_object_class,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=STATES.standard,
        )
        to_object_class = ObjectClass.objects.create(
            name="To Object CLass",
            definition="A definition",
            workgroup=self.wg1,
        )
        Status.objects.create(
            concept=to_object_class,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=STATES.standard
        )
        link = models.Link.objects.create(
            relation=see_also,
            root_item=root_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=root_object_class
        )
        self.login_viewer()
        response = self.client.get(root_object_class.get_absolute_url())

        self.assertContains(response, '<h2>Relations and Links</h2>')
        self.assertEqual(len(response.context['links_from']), 1)

    def test_link_viewable_from_non_root_under_to_links(self):
        # Make item2 viewable
        self.item2.workgroup = self.wg1
        self.item2.save()
        # Remove link 2
        self.link2.delete()

        self.login_viewer()
        response = self.reverse_get(
            'aristotle:item',
            reverse_args=[self.item2.id, 'objectclass', 'item2'],
            status_code=200
        )
        self.assertContains(response, '<h3>Links to this item</h3>')
        self.assertEqual(len(response.context['links_to']), 1)

    def test_arity_prop_2_roles(self):
        self.assertEqual(self.relation.arity, 2)

    def test_arity_prop_3_roles(self):
        rr3 = models.RelationRole.objects.create(
            name='New Role',
            definition='So New',
            ordinal=3,
            relation=self.relation
        )
        self.assertEqual(self.relation.arity, 3)

    def test_saving_more_items_than_multiplicity_allows(self):

        self.relation_role1.multiplicity = 2
        self.relation_role1.save()
        self.relation_role2.multiplicity = 2
        self.relation_role2.save()

        self.register_relation()
        self.login_editor()

        newitem = ObjectClass.objects.create(
            name='Third item',
            definition='The third one',
            workgroup=self.wg1
        )

        wizard_data = [
            {
                'relation': str(self.relation.pk)
            },
            {
                self.role1key: [self.item1.pk, self.item3.pk, newitem.pk],
                self.role2key: [self.item3.pk]
            }
        ]
        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_links:add_link', args=[self.item1.id]),
            'add_link_wizard'
        )

        self.assertEqual(response.status_code, 200)
        self.assertWizardStep(response, 1)  # Still on step 2
        errors = response.context['form'].errors
        self.assertEqual(errors[self.role1key], ["Only 2  metadata items are valid for the role 'part1'"])
        self.assertFalse(self.role2key in errors)

    def test_not_allowed_item_and_wrong_multiplicity(self):
        # wrong item is removed from cleaned_data before
        # multiplicity is checked (only if >1)
        self.relation_role1.multiplicity = 2
        self.relation_role1.save()

        self.register_relation()
        self.login_editor()

        wizard_data = [
            {
                'relation': str(self.relation.pk)
            },
            {
                self.role1key: self.item2.pk,
                self.role2key: self.item1.pk
            }
        ]

        response = self.post_to_wizard(
            wizard_data,
            reverse('aristotle_mdr_links:add_link', args=[self.item1.id]),
            'add_link_wizard'
        )

        self.assertEqual(response.status_code, 200)
        self.assertWizardStep(response, 1)  # Still on step 1 due to error
        errors = response.context['form'].errors
        self.assertTrue(self.role1key in errors)
        self.assertFalse(self.role2key in errors)


class TestLinkPerms(LinkTestBase, TestCase):
    def test_superuser_can_edit_links(self):
        user = self.su
        self.assertTrue(perms.user_can_change_link(user, self.link1))
        self.assertTrue(perms.user_can_change_link(user, self.link2))

    def test_editor_can_edit_some_links(self):
        user = self.editor
        self.assertTrue(perms.user_can_change_link(user, self.link1))
        self.assertFalse(perms.user_can_change_link(user, self.link2))

    def test_viewer_can_edit_no_links(self):
        user = self.viewer
        self.assertFalse(perms.user_can_change_link(user, self.link1))
        self.assertFalse(perms.user_can_change_link(user, self.link2))

    def test_registrar_can_edit_no_links(self):
        user = self.registrar
        self.assertFalse(perms.user_can_change_link(user, self.link1))
        self.assertFalse(perms.user_can_change_link(user, self.link2))

    def test_who_can_make_links(self):
        # Anyone who has an active account is an editor, so everyone can make links
        self.assertTrue(perms.user_can_make_link(self.registrar))
        self.assertTrue(perms.user_can_make_link(self.viewer))
        self.assertTrue(perms.user_can_make_link(self.editor))
        self.assertTrue(perms.user_can_make_link(self.su))

    def test_cannot_save_linkend_with_bad_role(self):
        self.new_relation = models.Relation.objects.create(
            name="another_test_relation", definition="Used for testing",
        )

        self.new_link = models.Link.objects.create(
            relation=self.new_relation,
            root_item=self.item1
        )
        self.assertNotEqual(self.new_link.relation, self.relation_role1.relation)

        with self.assertRaises(ValidationError):
            self.link_end_bad = self.new_link.add_link_end(
                role=self.relation_role1,
                concept=self.item1
            )


class TestLinkAssortedPages(LinkTestBase, TestCase):
    def test_link_json_page(self):
        self.login_superuser()
        response = self.client.get(reverse('aristotle_mdr_links:link_json_for_item', args=[self.item1.pk]))
        self.assertEqual(response.status_code, 200)


class TestLinksConceptPages(LinkTestBase, TestCase):
    def test_links_already_displayed_in_relationships_arent_duplicated(self):
        """Check that when identical links are created from A->B and from B->A, that when the Item page for
           A is viewed, that the additional link from B->A is not displayed"""
        # Create a relation
        see_also = models.Relation.objects.create(name="See Also", definition="See Also")
        # Create a related role
        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        # Owning item
        owning_object_class = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        to_object_class = ObjectClass.objects.create(
            name="To Object CLass",
            definition="A definition",
            workgroup=self.wg1,
        )
        owning_link = models.Link.objects.create(
            relation=see_also,
            root_item=owning_object_class
        )
        owning_linkend_1 = owning_link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        owning_linkend_2 = owning_link.add_link_end(
            role=see_also_role,
            concept=owning_object_class
        )

        to_link = models.Link.objects.create(
            relation=see_also,
            root_item=to_object_class
        )
        to_linkend_1 = to_link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        to_linkend_2 = to_link.add_link_end(
            role=see_also_role,
            concept=owning_object_class
        )
        # Go to the concept view page
        self.login_viewer()
        response = self.client.get(owning_object_class.get_absolute_url())

        self.assertEqual(response.status_code, 200)

        # Assert that the to_link has been removed
        self.assertEqual(response.context['links_to'], [])

    def test_permission_checking_on_link_for_unauthenticated_user(self):
        """Check that a link to an item the user does not have permission to see is not published"""
        see_also = models.Relation.objects.create(name="See Also", definition="See Also")
        # Create a related role
        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        # Root object class
        root_object_class = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        # Make the main item publicly accessible
        Status.objects.create(
            concept=root_object_class,
            registrationAuthority=self.ra,
            registrationDate=datetime.date(2000, 1, 1),
            state=STATES.standard,
        )
        to_object_class = ObjectClass.objects.create(
            name="To Object CLass",
            definition="A definition",
            workgroup=self.wg1,
        )
        link = models.Link.objects.create(
            relation=see_also,
            root_item=root_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=to_object_class
        )
        link.add_link_end(
            role=see_also_role,
            concept=root_object_class
        )
        self.logout()
        response = self.client.get(root_object_class.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        # Assert that the to_link has been removed for the unauthenticated user
        self.assertEqual(response.context['links_from'], [])
        self.assertEqual(response.context['links_to'], [])

        # Assert that the link is there for a superuser
        self.login_superuser()
        response = self.client.get(root_object_class.get_absolute_url())
        self.assertEqual(response.context['links_from'], [link])

    def test_superuser_can_delete_link(self):
        see_also = models.Relation.objects.create(name="See Also", definition="See Also")
        # Create a related role
        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        oc = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        link = models.Link.objects.create(
            relation=see_also,
            root_item=oc
        )
        link_pk = link.pk
        self.login_superuser()
        response = self.client.post(reverse("aristotle_mdr_links:remove_link", args=[link.pk, oc.pk]))
        self.assertEqual(response.status_code, 302)

        # Confirm that link has been deleted
        self.assertEqual(models.Link.objects.filter(pk=link_pk).count(), 0)

    def test_anonymous_user_cannot_delete_link(self):
        see_also = models.Relation.objects.create(name="See Also", definition="See Also")
        see_also_role = models.RelationRole.objects.create(
            name="Related",
            definition="Related",
            multiplicity=1,
            ordinal=1,
            relation=see_also
        )
        oc = ObjectClass.objects.create(
            name="Owning Item",
            definition="Definition",
            workgroup=self.wg1,
        )
        link = models.Link.objects.create(
            relation=see_also,
            root_item=oc
        )
        link_pk = link.pk
        self.logout()
        confirm_delete_link = reverse("aristotle_mdr_links:remove_link", args=[link.pk, oc.pk])

        # Test that getting the link delete view redirects to login
        response = self.client.get(confirm_delete_link)
        self.assertRedirects(response, f"{reverse('friendly_login')}?next={confirm_delete_link}")

        # Test that POSTing to the link delete view redirects to login
        response = self.client.post(reverse("aristotle_mdr_links:remove_link", args=[link.pk, oc.pk]))
        self.assertEqual(response.status_code, 302)

        # Confirm that link was not deleted
        self.assertEqual(models.Link.objects.filter(pk=link.pk).count(), 1)
