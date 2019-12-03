from unittest import skip
from django.test import TestCase, tag
from django.urls import reverse
from django.core.management import call_command

import aristotle_mdr.models as models
from aristotle_mdr.contrib.slots.models import Slot
from aristotle_mdr.contrib.custom_fields.models import CustomField, CustomValue
import aristotle_mdr.tests.utils as utils
from aristotle_mdr.utils import url_slugify_concept


class HaystackReindexMixin(object):
    def tearDown(self):
        call_command('clear_index', interactive=False, verbosity=0)

    def setUp(self):
        super().setUp()
        import haystack
        haystack.connections.reload('default')


class CreateListPageTests(utils.LoggedInViewPages, TestCase):
    def test_create_list_active(self):
        self.logout()
        response = self.client.get(reverse('aristotle:create_list'))
        self.assertEqual(response.status_code, 302)  # redirect to login

        self.login_viewer()
        response = self.client.get(reverse('aristotle:create_list'))
        self.assertEqual(response.status_code, 200)

        self.login_registrar()
        response = self.client.get(reverse('aristotle:create_list'))
        self.assertEqual(response.status_code, 200)

        self.login_editor()
        response = self.client.get(reverse('aristotle:create_list'))
        self.assertEqual(response.status_code, 200)


class ConceptWizard_TestInvalidUrls(HaystackReindexMixin, utils.LoggedInViewPages, TestCase):
    def test_invalid_model(self):
        url = reverse('aristotle:createItem', args=["invalid_model_name"])
        self.login_editor()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        url = reverse('aristotle:createItem', args=["objectclass"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_app_and_model(self):
        url = reverse('aristotle:createItem', args=["invalid_app_name", "invalid_model_name"])
        self.login_editor()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        url = reverse('aristotle:createItem', args=["aristotle_mdr", "objectclass"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ConceptWizardPage(HaystackReindexMixin, utils.AristotleTestUtils):
    wizard_name="Harry Potter"  # This used to be needed, now its not. We kept it cause its funny.
    wizard_form_name="dynamic_aristotle_wizard"
    extra_step2_data = {}
    step_names = ['initial', 'results']

    def setUp(self):
        super().setUp()
        # import haystack
        # haystack.connections.reload('default')

        # Tests against bug #333
        # https://github.com/aristotle-mdr/aristotle-metadata-registry/issues/333
        self.extra_wg = models.Workgroup.objects.create(name="Extra WG for issue 333", stewardship_organisation=self.steward_org_1)
        self.extra_wg.giveRoleToUser('steward', self.editor)
        self.extra_wg.save()

    @property
    def wizard_url(self):
        return reverse('aristotle:createItem', args=[self.model._meta.app_label, self.model._meta.model_name])

    def test_anonymous_cannot_view_create_page(self):
        self.logout()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 302)

    def test_viewer_can_view_create_page(self):
        self.login_viewer()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)

    def test_regular_user_can_view_create_page(self):
        # Thanks @stevenmce for pointing this out
        self.login_regular_user()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)

    def test_registrar_cannot_view_create_page(self):
        self.login_registrar()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)

    def test_editor_can_view_create_page(self):
        self.login_editor()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)

    def do_test_for_issue333(self, response):
        self.assertTrue(self.extra_wg in response.context['form'].fields['workgroup'].queryset)

    @tag('wizardobj')
    def test_editor_can_make_object(self):
        self.login_editor()
        step_1_data = {
            self.wizard_form_name + '-current_step': 'initial',
            'initial-name': 'Test Item'
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'results')

        self.do_test_for_issue333(response)

        step_2_data = {
            self.wizard_form_name + '-current_step': 'results',
            'results-name': "Test Item",
            'results-definition': "Test Definition",
        }
        management_forms = utils.get_management_forms(self.model, item_is_model=True, slots=True)
        step_2_data.update(management_forms)
        step_2_data.update(self.extra_step2_data)

        # But we are using a non-permitted workgroup.
        step_2_data.update({
            'results-workgroup': self.wg2.id
            })
        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # must submit a definition at this step. With the right workgroup
        step_2_data.update({
            'results-definition': "Test Definition",
            'results-workgroup': self.wg1.id
            })
        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(models._concept.objects.filter(name="Test Item").exists())
        self.assertEqual(models._concept.objects.filter(name="Test Item").count(), 1)
        item = models._concept.objects.filter(name="Test Item").first()
        self.assertRedirects(response, url_slugify_concept(item))

    @tag('wizardobjslots')
    def test_editor_can_make_object_with_slots(self):
        wizard_data = [
            {
                'dynamic_aristotle_wizard-current_step': 'initial',
                'initial-name': 'My new object'
            },
            {
                'dynamic_aristotle_wizard-current_step': 'results',
                'results-name': 'My new object',
                'results-definition': 'Brand new'
            }
        ]
        slots_data = [
            {'name': 'Extra', 'type': 'String', 'value': 'SomeExtraData',
             'order': 0, 'permission': 0}
        ]

        formsets = utils.get_management_forms(self.model, item_is_model=True)
        formsets.update(self.get_formset_postdata(slots_data, 'slots'))
        wizard_data[1].update(formsets)

        self.login_editor()
        response = self.post_direct_to_wizard(
            wizard_data,
            self.wizard_url,
            self.step_names
        )
        self.assertEqual(response.status_code, 302)
        item = models._concept.objects.get(name='My new object')
        self.assertEqual(item.definition, 'Brand new')
        slot = Slot.objects.get(
            concept=item,
            name='Extra'
        )
        self.assertEqual(slot.value, 'SomeExtraData')

    @tag('wizardobjcf')
    def test_editor_can_make_object_with_custom_values(self):
        cf = CustomField.objects.create(
            order=0,
            name='ExtraInfo',
            type='str',
        )

        cf_field_name = 'results-{}'.format(cf.form_field_name)
        wizard_data = [
            {
                'dynamic_aristotle_wizard-current_step': 'initial',
                'initial-name': 'My new object'
            },
            {
                'dynamic_aristotle_wizard-current_step': 'results',
                'results-name': 'My new object',
                'results-definition': 'Brand new',
                cf_field_name: 'SomeExtraInformation'
            }
        ]
        formsets = utils.get_management_forms(self.model, item_is_model=True, slots=True)
        wizard_data[1].update(formsets)

        self.login_editor()
        response = self.post_direct_to_wizard(
            wizard_data,
            self.wizard_url,
            self.step_names
        )
        self.assertEqual(response.status_code, 302)

        concept = models._concept.objects.get(name='My new object')
        cv = CustomValue.objects.get(
            concept=concept,
            field=cf
        )
        self.assertEqual(cv.content, 'SomeExtraInformation')

    def test_editor_can_make_object__where_item_already_has_duplicate_name(self):
        self.item_existing = self.model.objects.create(
            name='Already exists',
            definition="This item already exists",
            workgroup=self.wg1
        )
        # Need to make sure its public
        self.ra.register(
            item=self.item_existing,
            state=models.STATES.standard,
            user=self.su
        )

        self.login_editor()
        self.assertTrue(self.item_existing.can_view(self.editor))
        form_data = {
            self.wizard_form_name + '-current_step': 'initial',
            'initial-name': "Already exists",
        }
        # success!

        response = self.client.post(self.wizard_url, form_data)
        wizard = response.context['wizard']

        self.assertTrue(len(wizard['form'].errors.keys()) == 0)
        self.assertTrue(self.item_existing in response.context['duplicate_items'])

        # Existing item should show up in the "similar results page"
        self.assertContains(response, self.item_existing.definition)

    def test_editor_can_make_object__where_item_already_has_similar_details(self):
        from reversion.revisions import create_revision
        with create_revision():
            # Need to wrap this in a revision to make sure the search is updated
            self.item_existing = self.model.objects.create(
                name='Almost the same',
                definition="This item already exists",
                workgroup=self.wg1
            )
            # Need to make sure its public
            self.ra.register(
                item=self.item_existing,
                state=models.STATES.standard,
                user=self.su
            )

        self.login_editor()
        self.assertTrue(self.item_existing.can_view(self.editor))
        form_data = {
            self.wizard_form_name+'-current_step': 'initial',
            'initial-name': "Already exists",
        }
        # success!

        response = self.client.post(self.wizard_url, form_data)
        wizard = response.context['wizard']
        self.assertTrue(len(wizard['form'].errors.keys()) == 0)
        self.assertFalse('duplicate_items' in response.context.keys())

        self.assertTrue(
            self.item_existing.pk in [
                x.object.pk for x in response.context['similar_items']
            ]
        )

        # Existing item should show up in the "similar results page"
        self.assertContains(response, self.item_existing.definition)


class ObjectClassWizardPage(ConceptWizardPage, TestCase):
    model = models.ObjectClass


class PropertyWizardPage(ConceptWizardPage, TestCase):
    model = models.Property


class ConceptualDomainWizardPage(ConceptWizardPage, TestCase):
    model = models.ConceptualDomain

    def post_first_step(self):
        item_name = 'My Shiny New Conceptual Domain'
        step_1_data = {
            self.wizard_form_name+'-current_step': 'initial',
            'initial-name': item_name,
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'results')

        return item_name

    @tag('edit_formsets')
    def test_weak_editor_during_create(self):

        self.login_editor()
        item_name = self.post_first_step()

        step_2_data = {
            self.wizard_form_name+'-current_step': 'results',
            'initial-name':item_name,
            'results-name':item_name,
            'results-definition':"Test Definition",
        }

        valuemeaning_formset_data = [
            {'name': 'Test1', 'definition': 'test defn', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 0},
            {'name': 'Test2', 'definition': 'test defn', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(valuemeaning_formset_data, 'value_meaning', 0))
        step_2_data.update(self.get_formset_postdata([], 'slots'))
        step_2_data.update(self.get_formset_postdata([], 'org_records'))

        response = self.client.post(self.wizard_url, step_2_data)

        self.assertEqual(response.status_code, 302)

        self.assertTrue(self.model.objects.filter(name=item_name).exists())
        self.assertEqual(self.model.objects.filter(name=item_name).count(), 1)
        item = self.model.objects.filter(name=item_name).first()
        self.assertRedirects(response,url_slugify_concept(item))

        vms = item.valuemeaning_set.all()

        self.assertEqual(len(vms), 2)
        self.assertEqual(vms[0].name, 'Test1')
        self.assertEqual(vms[1].name, 'Test2')

    @tag('edit_formsets', 'runthis')
    def test_wizard_error_display(self):

        self.login_editor()
        item_name = self.post_first_step()

        step_2_data = {
            self.wizard_form_name+'-current_step': 'results',
            'initial-name': item_name,
            'results-name': item_name,
            'results-definition': "Test Definition",
        }

        # Post with a blank name
        valuemeaning_formset_data = [
            {'name': '', 'definition': 'test defn', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 0},
            {'name': 'Test2', 'definition': 'test defn', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(valuemeaning_formset_data, 'value_meaning', 0))
        step_2_data.update(self.get_formset_postdata([], 'slots'))
        step_2_data.update(self.get_formset_postdata([], 'org_records'))

        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['weak_formsets'][0]['formset'].errors[0], {'name': ['This field is required.']})
        self.assertContains(response, 'This field is required.')


class ValueDomainWizardPage(ConceptWizardPage, TestCase):
    model = models.ValueDomain

    @tag('edit_formsets')
    def test_weak_editor_during_create(self):

        self.login_editor()

        item_name = 'My Shiny New Value Domain'
        step_1_data = {
            self.wizard_form_name+'-current_step': 'initial',
            'initial-name': item_name,
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'results')

        step_2_data = {
            self.wizard_form_name+'-current_step': 'results',
            'initial-name': item_name,
            'results-name': item_name,
            'results-definition': "Test Definition",
        }
        step_2_data.update(self.get_formset_postdata([], 'slots'))

        step_2_data.update(self.get_formset_postdata([], 'org_records'))

        permissible_formset_data = [
            {'value': 'Test1', 'meaning': 'Test1', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 0},
            {'value': 'Test2', 'meaning': 'Test2', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(permissible_formset_data, 'permissible_values', 0))

        supplementary_formset_data = [
            {'value': 'Test3', 'meaning': 'Test3', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 0},
            {'value': 'Test4', 'meaning': 'Test4', 'start_date': '1999-01-01', 'end_date': '2090-01-01', 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(supplementary_formset_data, 'supplementary_values', 0))

        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(self.model.objects.filter(name=item_name).exists())
        self.assertEqual(self.model.objects.filter(name=item_name).count(), 1)
        item = self.model.objects.filter(name=item_name).first()
        self.assertRedirects(response, url_slugify_concept(item))

        supvals = item.supplementaryvalue_set.all()
        permvals = item.permissiblevalue_set.all()

        self.assertEqual(len(supvals), 2)
        self.assertEqual(supvals[0].value, 'Test3')
        self.assertEqual(supvals[1].value, 'Test4')

        self.assertEqual(len(permvals), 2)
        self.assertEqual(permvals[0].value, 'Test1')
        self.assertEqual(permvals[1].value, 'Test2')


class DataElementConceptWizardPage(ConceptWizardPage, TestCase):
    model = models.DataElementConcept


class DataElementWizardPage(ConceptWizardPage, TestCase):
    model = models.DataElement


class DataElementDerivationWizardPage(ConceptWizardPage, TestCase):
    model = models.DataElementDerivation

    @tag('edit_formsets')
    def test_derivation_m2m_during_create(self):

        self.de1 = models.DataElement.objects.create(name='DE1 - visible', definition="my definition", workgroup=self.wg1)
        self.de2 = models.DataElement.objects.create(name='DE2 - visible', definition="my definition", workgroup=self.wg1)
        self.de3 = models.DataElement.objects.create(name='DE3 - visible', definition="my definition", workgroup=self.wg1)

        self.login_editor()

        item_name = 'My New DED Test Item'
        step_1_data = {
            self.wizard_form_name+'-current_step': 'initial',
            'initial-name': item_name,
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'results')

        step_2_data = {
            self.wizard_form_name+'-current_step': 'results',
            'initial-name': item_name,
            'results-name': item_name,
            'results-definition': "Test Definition",
        }
        step_2_data.update(self.get_formset_postdata([], 'slots'))
        step_2_data.update(self.get_formset_postdata([], 'org_records'))

        inputs_formset_data = [
            {'data_element': self.de3.pk, 'ORDER': 0},
            {'data_element': self.de1.pk, 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(inputs_formset_data, 'inputs', 0))

        derives_formset_data = [
            {'data_element': self.de2.pk, 'ORDER': 0},
            {'data_element': self.de3.pk, 'ORDER': 1}
        ]
        step_2_data.update(self.get_formset_postdata(derives_formset_data, 'derives', 0))

        response = self.client.post(self.wizard_url, step_2_data)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(self.model.objects.filter(name=item_name).exists())
        self.assertEqual(self.model.objects.filter(name=item_name).count(), 1)
        item = self.model.objects.filter(name=item_name).first()
        self.assertRedirects(response, url_slugify_concept(item))

        inputs = item.input_data_elements.all()
        derives = item.derived_data_elements.all()

        self.assertEqual(len(inputs), 2)
        self.assertTrue(self.de3 in inputs)
        self.assertTrue(self.de1 in inputs)

        self.assertEqual(len(derives), 2)
        self.assertTrue(self.de2 in derives)
        self.assertTrue(self.de3 in derives)

        self.assertEqual(models.DedInputsThrough.objects.count(), 2)
        self.assertEqual(models.DedInputsThrough.objects.get(order=0).data_element, self.de3)
        self.assertEqual(models.DedInputsThrough.objects.get(order=1).data_element, self.de1)

        self.assertEqual(models.DedDerivesThrough.objects.count(), 2)
        self.assertEqual(models.DedDerivesThrough.objects.get(order=0).data_element, self.de2)
        self.assertEqual(models.DedDerivesThrough.objects.get(order=1).data_element, self.de3)


class DataElementConceptAdvancedWizardPage(HaystackReindexMixin, utils.AristotleTestUtils, TestCase):
    wizard_url_name = "createDataElementConcept"
    wizard_form_name = "data_element_concept_wizard"
    model = models.DataElementConcept

    @property
    def wizard_url(self):
        return reverse('aristotle:%s' % self.wizard_url_name)

    def test_show_slots_tab_false(self):
        self.login_editor()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('show_slots_tab' in response.context)
        self.assertFalse(response.context['show_slots_tab'])

    def test_editor_can_make_object__has_prior_components(self):
        self.login_editor()
        from reversion.revisions import create_revision
        with create_revision():
            ani = models.ObjectClass.objects.create(name="animagus", definition="my animagus definition", workgroup=self.wg1)
            at = models.Property.objects.create(name="animal type", definition="my definition", workgroup=self.wg1)

        step_1_data = {
            self.wizard_form_name+'-current_step': 'component_search',
            'component_search-oc_name': "animagus",
            'component_search-pr_name': "animal"
        }
        # success!

        response = self.client.post(self.wizard_url, step_1_data)
        self.assertContains(response, ani.definition)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertDelayedEqual(len(wizard['form'].fields.keys()), 2)  # we should have a match for OC and P

        step_2_data = {}
        step_2_data.update(step_1_data)
        step_2_data.update({self.wizard_form_name+'-current_step': 'component_results'})

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')

        # Must pick an Object Class and Property (or none) to continue.
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())

        # Try the wrong way around
        step_2_data.update({'component_results-oc_options': at.pk, 'component_results-pr_options': ani.pk})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())

        # Picking the correct options should send us to the DEC results page.
        step_2_data.update({'component_results-oc_options':str(ani.pk), 'component_results-pr_options': str(at.pk)})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'find_dec_results')

    def test_editor_can_make_object__no_prior_components(self):
        self.login_editor()
        step_1_data = {
            self.wizard_form_name+'-current_step': 'component_search',
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'component_search')
        self.assertTrue('oc_name' in wizard['form'].errors.keys())
        self.assertTrue('pr_name' in wizard['form'].errors.keys())

        # must submit a name
        step_1_data.update({'component_search-oc_name': "Animagus"})
        step_1_data.update({'component_search-pr_name': "Animal type"})
        # success!

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertContains(response, "No matching object classes were found")
        self.assertContains(response, "No matching properties were found")

        step_2_data = {
            self.wizard_form_name+'-current_step': 'component_results',
        }  # nothing else needed, as we aren't picking a component.

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'make_oc')

        # Now we make the object class
        step_3_data = {
            self.wizard_form_name+'-current_step': 'make_oc',
            'make_oc-name': "Animagus",
            'make_oc-definition': "A wizard who can change shape.",
        }

        # we are using a non-permitted workgroup.
        step_3_data.update({
            'make_oc-workgroup': self.wg2.id
            })
        response = self.client.post(self.wizard_url, step_3_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # With the right workgroup
        step_3_data.update({
            'make_oc-workgroup': self.wg1.id
            })
        response = self.client.post(self.wizard_url, step_3_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'make_p')

        # Now we make the property
        step_4_data = {
            self.wizard_form_name+'-current_step': 'make_p',
            'make_p-name': "Animal type",
            'make_p-definition': "A wizard who can change shape.",
            'make_p-workgroup': self.wg2.pk
        }

        # we are using a non-permitted workgroup.
        response = self.client.post(self.wizard_url, step_4_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # With the right workgroup
        step_4_data.update({
            'make_p-workgroup': self.wg1.pk
            })
        response = self.client.post(self.wizard_url, step_4_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'find_dec_results')

        step_4_data.update(step_3_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(response.context['form'].initial['name'], 'Animagus--Animal type')

        step_5_data = {}
        step_5_data.update(step_4_data)
        step_5_data.update({self.wizard_form_name+'-current_step': 'find_dec_results', })

        response = self.client.post(self.wizard_url, step_5_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('name' in wizard['form'].errors.keys())
        # NOWG self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # must submit a name and definition at this step. But we are using a non-permitted workgroup.
        step_5_data.update({
            'find_dec_results-name': "Animagus--Animal type",
            'find_dec_results-definition': "The record of the shape a wizard can change into.",
            'find_dec_results-workgroup': self.wg2.pk
            })
        response = self.client.post(self.wizard_url, step_5_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # must submit a definition at this step. With the right workgroup
        step_5_data.update({
            'find_dec_results-workgroup': self.wg1.pk
            })
        response = self.client.post(self.wizard_url, step_5_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'completed')

        # now save everything
        step_6_data = {}
        step_6_data.update(step_5_data)
        step_6_data.update({
            self.wizard_form_name+'-current_step': 'completed',
        })

        response = self.client.post(self.wizard_url, step_6_data)
        wizard = response.context['wizard']
        self.assertTrue('make_items' in wizard['form'].errors.keys())
        self.assertFalse(models.DataElementConcept.objects.filter(name="Animagus--Animal type").exists())
        step_6_data.update({
            self.wizard_form_name+'-current_step': 'completed',
            'completed-make_items': True
            })
        response = self.client.post(self.wizard_url, step_6_data)
        self.assertTrue(models.DataElementConcept.objects.filter(name="Animagus--Animal type").exists())
        item = models.DataElementConcept.objects.filter(name="Animagus--Animal type").first()
        self.assertRedirects(response, url_slugify_concept(item))

    def test_component_initial(self):
        """Test that components tab hidden in final step when reusing"""

        # Make an oc and prop to reuse
        oc = models.ObjectClass.objects.create(
            name='Computer',
            definition='a computing device',
            workgroup=self.wg1
        )
        prop = models.Property.objects.create(
            name='Speediness',
            definition='vroroormeoroemrem',
            workgroup=self.wg1
        )

        steps = [
            'component_search',
            'component_results'
        ]
        data = [
            {'oc_name': 'Computer', 'pr_name': 'Speediness'},
            {'oc_options': str(oc.id), 'pr_options': str(prop.id)}
        ]

        self.login_editor()
        response = self.post_to_wizard(data, self.wizard_url, self.wizard_form_name, steps)
        self.assertWizardStep(response, 'find_dec_results')
        self.assertTrue('hide_components_tab' in response.context)
        self.assertTrue(response.context['hide_components_tab'])


class DataElementAdvancedWizardPage(HaystackReindexMixin, utils.LoggedInViewPages, TestCase):
    wizard_url_name="createDataElement"
    wizard_form_name="data_element_wizard"
    model=models.DataElement

    @property
    def wizard_url(self):
        return reverse('aristotle:%s' % self.wizard_url_name)

    def test_show_slots_tab_false(self):
        self.login_editor()
        response = self.client.get(self.wizard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('show_slots_tab' in response.context)
        self.assertFalse(response.context['show_slots_tab'])

    def test_editor_can_make_object__has_prior_components(self):
        self.login_editor()

        from reversion.revisions import create_revision
        with create_revision():
            ani = models.ObjectClass.objects.create(name="animagus", definition="my definition", workgroup=self.wg1)
            at = models.Property.objects.create(name="animal type", definition="my definition", workgroup=self.wg1)
            momat = models.ValueDomain.objects.create(name="MoM animal type classification",
                    definition="Ministry of Magic standard classification of animagus animal types", workgroup=self.wg1)
            models.DataElementConcept.objects.create(
                name="animagus--animal type",
                definition="my definition",
                workgroup=self.wg1,
                objectClass=ani,
                property=at
            )

        step_1_data = {
            self.wizard_form_name+'-current_step': 'component_search',
            'component_search-oc_name': "animagus",
            'component_search-pr_name': "animal",
            'component_search-vd_name': "mom classification"
        }
        # success!

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertDelayedEqual(len(wizard['form'].fields.keys()), 3)  # we should have a match for OC, P and VD

        step_2_data = {}
        step_2_data.update(step_1_data)
        step_2_data.update({self.wizard_form_name+'-current_step': 'component_results'})

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')

        # Must pick an Object Class and Property (or none) to continue.
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())
        self.assertTrue('vd_options' in wizard['form'].errors.keys())

        # Try the wrong way around
        step_2_data.update({'component_results-oc_options': at.pk, 'component_results-pr_options': momat.pk,
                            'component_results-vd_options': ani.pk})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())
        self.assertTrue('vd_options' in wizard['form'].errors.keys())

        # Picking the correct options should send us to the DEC results page.
        step_2_data.update({'component_results-oc_options': str(ani.pk),
                            'component_results-pr_options': str(at.pk),
                            'component_results-vd_options': str(momat.pk)})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'find_dec_results')  # There is a matching DEC
        step_3_data = {}
        step_3_data.update(step_2_data)
        step_3_data.update({self.wizard_form_name+'-current_step': 'find_dec_results'})
        response = self.client.post(self.wizard_url, step_3_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'find_dec_results')

    def test_editor_can_make_object__has_prior_components_but_no_dec(self):
        self.login_editor()
        from reversion.revisions import create_revision
        with create_revision():
            ani = models.ObjectClass.objects.create(name="animagus", definition="my definition", workgroup=self.wg1)
            at = models.Property.objects.create(name="animal type", definition="my definition", workgroup=self.wg1)
            momat = models.ValueDomain.objects.create(
                name="MoM animal type classification",
                definition="Ministry of Magic standard classification of animagus animal types",
                workgroup=self.wg1
            )

        step_1_data = {
            self.wizard_form_name+'-current_step': 'component_search',
            'component_search-oc_name': "animagus",
            'component_search-pr_name': "animal",
            'component_search-vd_name': "mom classification"
        }
        # success!

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertDelayedEqual(len(wizard['form'].fields.keys()), 3)  # we should have a match for OC, P and VD

        step_2_data = {}
        step_2_data.update(step_1_data)
        step_2_data.update({self.wizard_form_name+'-current_step': 'component_results'})

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')

        # Must pick an Object Class and Property (or none) to continue.
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())
        self.assertTrue('vd_options' in wizard['form'].errors.keys())

        # Try the wrong way around
        step_2_data.update({'component_results-oc_options':at.pk,
                            'component_results-pr_options': momat.pk,
                            'component_results-vd_options':ani.pk})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertTrue('oc_options' in wizard['form'].errors.keys())
        self.assertTrue('pr_options' in wizard['form'].errors.keys())
        self.assertTrue('vd_options' in wizard['form'].errors.keys())

        # Picking the correct options should send us to the DEC results page.
        step_2_data.update({'component_results-oc_options': str(ani.pk),
                            'component_results-pr_options': str(at.pk),
                            'component_results-vd_options': str(momat.pk)})
        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'make_dec')  # Jump straight to make DEC, as no matching will be found.

        # Now we make the Data Element Concept
        step_3_data = {}
        step_3_data.update(step_2_data)
        step_3_data = {
            self.wizard_form_name+'-current_step': 'make_dec',
            'make_dec-name': "Animagus--Animal type",
            'make_dec-definition': "The record of the shape a wizard can change into.",
        }

        # we are using a non-permitted workgroup.
        step_3_data.update({
            'make_dec-workgroup': self.wg2.pk
            })
        response = self.client.post(self.wizard_url, step_3_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # With the right workgroup
        step_3_data.update({
            'make_dec-workgroup': self.wg1.id
            })
        response = self.client.post(self.wizard_url, step_3_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'find_de_results')

        # Now we make the Data Element
        step_4_data = {}
        step_4_data.update(step_3_data)
        step_4_data = {
            self.wizard_form_name+'-current_step': 'find_de_results',
            'find_de_results-name': "Animagus--Animal type, MoM Code",
            'find_de_results-definition': "The record of the shape a wizard can change into.",
        }

        # we are using a non-permitted workgroup.
        step_4_data.update({
            'find_de_results-workgroup': self.wg2.pk
            })
        response = self.client.post(self.wizard_url, step_4_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # With the right workgroup
        step_4_data.update({
            'find_de_results-workgroup': self.wg1.pk
            })
        response = self.client.post(self.wizard_url, step_4_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'completed')

        # Now we save the whole thing
        step_5_data = {}
        step_5_data.update(step_4_data)
        step_5_data.update({
            self.wizard_form_name+'-current_step': 'completed',
        })

        response = self.client.post(self.wizard_url, step_5_data)
        wizard = response.context['wizard']
        self.assertTrue('make_items' in wizard['form'].errors.keys())
        self.assertFalse(models.DataElementConcept.objects.filter(name="Animagus--Animal type").exists())
        self.assertFalse(models.DataElement.objects.filter(name="Animagus--Animal type, MoM Code").exists())
        step_5_data.update({
            'completed-make_items': True
            })
        response = self.client.post(self.wizard_url, step_5_data)
        item = models.DataElement.objects.filter(name="Animagus--Animal type, MoM Code").first()
        self.assertRedirects(response,url_slugify_concept(item))

        self.assertTrue(models.DataElementConcept.objects.filter(name="Animagus--Animal type").exists())
        self.assertTrue(models.DataElement.objects.filter(name="Animagus--Animal type, MoM Code").exists())

    @skip('Test needs to be updated')
    def test_editor_can_make_object__no_prior_components(self):
        self.login_editor()
        step_1_data = {
            self.wizard_form_name+'-current_step': 'component_search',
        }

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'component_search')
        self.assertTrue('oc_name' in wizard['form'].errors.keys())
        self.assertTrue('pr_name' in wizard['form'].errors.keys())

        # must submit a name
        step_1_data.update({'component_search-oc_name': "Animagus"})
        step_1_data.update({'component_search-pr_name': "Animal type"})
        # success!

        response = self.client.post(self.wizard_url, step_1_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertEqual(wizard['steps'].current, 'component_results')
        self.assertContains(response, "No matching object classes were found")
        self.assertContains(response, "No matching properties were found")

        step_2_data = {
            self.wizard_form_name+'-current_step': 'component_results',
        } # nothing else needed, as we aren't picking a component.

        response = self.client.post(self.wizard_url, step_2_data)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'make_oc')

        # Now we make the object class
        step_3_data = {
            self.wizard_form_name+'-current_step': 'make_oc',
            'make_oc-name': "Animagus",
        }

        response = self.client.post(self.wizard_url, step_3_data)
        wizard = response.context['wizard']
        self.assertTrue('definition' in wizard['form'].errors.keys())
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # no "test item" yet.
        self.assertFalse(models._concept.objects.filter(name="Test Item").exists())

        # must submit a definition at this step. But we are using a non-permitted workgroup.
        step_3_data.update({
            'make_oc-definition': "A wizard who can change shape.",
            'make_oc-workgroup': self.wg2.pk
            })
        response = self.client.post(self.wizard_url, step_3_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # must submit a definition at this step. With the right workgroup
        step_3_data.update({
            'make_oc-workgroup': self.wg1.pk
            })
        response = self.client.post(self.wizard_url, step_3_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'make_p')

        # Now we make the property
        step_4_data = {
            self.wizard_form_name+'-current_step': 'make_p',
            'make_p-name': "Animal type",
        }

        response = self.client.post(self.wizard_url, step_4_data)
        wizard = response.context['wizard']
        self.assertTrue('definition' in wizard['form'].errors.keys())
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # no "test item" yet.
        self.assertFalse(models._concept.objects.filter(name="Test Item").exists())

        # must submit a definition at this step. But we are using a non-permitted workgroup.
        step_4_data.update({
            'make_p-definition': "A wizard who can change shape.",
            'make_p-workgroup': self.wg2.pk
            })
        response = self.client.post(self.wizard_url, step_4_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('workgroup' in wizard['form'].errors.keys())

        # must submit a definition at this step. With the right workgroup
        step_4_data.update({
            'make_p-workgroup': self.wg1.pk
            })
        response = self.client.post(self.wizard_url, step_4_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(wizard['steps'].current, 'find_dec_results')

        step_4_data.update(step_1_data)
        step_4_data.update(step_2_data)
        step_4_data.update(step_3_data)
        self.assertEqual(response.status_code, 200)
        wizard = response.context['wizard']
        self.assertEqual(response.context['form'].initial['name'], 'Animagus--Animal type')

        step_5_data = {}
        step_5_data.update(step_1_data)
        step_5_data.update(step_2_data)
        step_5_data.update(step_3_data)
        step_5_data.update(step_4_data)
        step_5_data.update({self.wizard_form_name+'-current_step': 'find_dec_results', })

        response = self.client.post(self.wizard_url, step_5_data)
        wizard = response.context['wizard']
        self.assertEqual(response.status_code, 200)
        self.assertTrue('name' in wizard['form'].errors.keys())


"""Ordinary. Wizarding. Level. Examinations. O.W.L.s. More commonly known as 'Owls'.
Study hard and you will be rewarded.
Fail to do so and the consequences may be... severe"""
