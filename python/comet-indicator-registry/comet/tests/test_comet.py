from django.test import TestCase, tag
from unittest import skip

from aristotle_mdr.tests.utils import ManagedObjectVisibility
from aristotle_mdr.tests.main.test_html_pages import LoggedInViewConceptPages
from aristotle_mdr.tests.main.test_admin_pages import AdminPageForConcept

from aristotle_mdr import models as MDR
from comet import models


def setUpModule():
    from django.core.management import call_command
    call_command('load_aristotle_help', verbosity=0)


class IndicatorVisibility(ManagedObjectVisibility, TestCase):
    def setUp(self):
        super(IndicatorVisibility, self).setUp()
        self.item = models.Indicator.objects.create(
            name="Test Indicator",
            workgroup=self.wg,
        )


class IndicatorAdmin(AdminPageForConcept, TestCase):
    itemType=models.Indicator


class IndicatorViewPage(LoggedInViewConceptPages, TestCase):
    url_name='indicator'
    itemType=models.Indicator

    @tag('perms')
    def test_component_permsission_checks(self):
        viewable = MDR.DataElement.objects.create(
            name='viewable data element', definition='Viewable', submitter=self.editor
        )
        invis = MDR.DataElement.objects.create(
            name='invisible data element', definition='Invisible'
        )
        self.item1.add_numerator(data_element=viewable)
        self.item1.add_numerator(data_element=viewable)
        self.item1.add_denominator(data_element=invis)

        self.login_editor()
        response = self.client.get(
            self.item1.get_absolute_url()
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(viewable.id in response.context['viewable_ids'])
        self.assertTemplateUsed(response, 'comet/indicator.html')

        self.assertContains(response, viewable.name)
        self.assertNotContains(response, invis.name)
        self.assertContains(response, 'You don\'t have permission', count=1)


    def test_weak_editing_in_advanced_editor_dynamic(self):
        de = MDR.DataElement.objects.create(
            name="test name",
            definition="test definition",
        )
        de.save()

        for i in range(4):
            self.item1.add_numerator(data_element=de)

        for i in range(3):
            self.item1.add_denominator(data_element=de)

        for i in range(2):
            self.item1.add_disaggregator(data_element=de)

        default_fields = {
            'data_element': de.id,
        }

        super().test_weak_editing_in_advanced_editor_dynamic(updating_field='description', default_fields=default_fields)
