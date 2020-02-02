from django.test import TestCase, override_settings
from django.conf import settings

from aristotle_mdr.tests.utils import model_to_dict_with_change_time, AristotleTestUtils
from aristotle_mdr.contrib.custom_fields.models import CustomValue, CustomField
from aristotle_mdr.contrib.custom_fields.types import type_choices as TYPE_CHOICES
import aristotle_mdr.models as MDR
import reversion
import json


@override_settings()
class SerializerTestCase(AristotleTestUtils, TestCase):
    def setUp(self):
        import aristotle_dse.models as DSE
        super().setUp()

        self.object_class = MDR.ObjectClass.objects.create(
            name='Person',
            definition='A human being',
            submitter=self.editor
        )

        self.data_element = MDR.DataElement.objects.create(
            name='Data Element',
            definition='This is a data element'
        )

        self.custom_field = CustomField.objects.create(
            order=1,
            name='A Custom Field',
            type=TYPE_CHOICES.str
        )

        self.custom_value = CustomValue.objects.create(
            field=self.custom_field,
            concept=self.object_class,
            content="Custom values"
        )

        aristotle_settings = settings.ARISTOTLE_SETTINGS
        aristotle_settings['CONTENT_EXTENSIONS'].append('aristotle_dse')
        with override_settings(ARISTOTLE_SETTINGS=aristotle_settings):
            self.data_set_specification = DSE.DataSetSpecification.objects.create(
                name='Person DSS',
                definition='A data set specification about people',
                submitter=self.editor
            )

            self.dss_de_inclusion = DSE.DSSDEInclusion(
                data_element=self.data_element,
                specific_information="Specific information",
                conditional_inclusion="Conditional",
                order=1,
                dss=self.data_set_specification
            )

    def create_version(self):
        with reversion.create_revision():
            self.object_class.definition = 'No longer a human being'
            self.object_class.name = 'New Person'
            self.object_class.save()

    def get_serialized_data_dict(self, concept):
        version = reversion.models.Version.objects.get_for_object(concept).first()
        return json.loads(version.serialized_data)

    def get_app_label(self, concept):
        return concept._meta.label_lower

    def test_basic_fields_serialized(self):
        """ Test that the basic concrete model fields were serialized """
        self.create_version()

        serialized_data = self.get_serialized_data_dict(self.object_class)

        # Confirm presence of basic fields in serialized data
        self.assertEqual(serialized_data['name'], 'New Person')
        self.assertEqual(serialized_data['definition'], 'No longer a human being')

    def test_model_class_serialized(self):
        """ Test that the model class was serialized"""
        self.create_version()

        serialized_data = self.get_serialized_data_dict(self.object_class)

        self.assertEqual(serialized_data['serialized_model'], self.get_app_label(self.object_class))

    def test_custom_fields_serialized(self):
        """ Test that the custom fields were serialized. This does not confirm that editor functionality
         is working correctly, merely that the serialization of custom fields is working"""
        with reversion.create_revision():
            self.object_class.name = 'New Person'
            self.custom_value.content = 'New content'
            self.custom_value.save()
            self.object_class.save()

        serialized_data = self.get_serialized_data_dict(self.object_class)

        self.assertEqual(serialized_data['customvalue_set'][0]['content'], 'New content')

    def test_custom_fields_serialized_from_concept_editor(self):
        """ Test that the custom fields were serialized from the editor"""
        object_class = MDR.ObjectClass.objects.create(
            name='Person',
            definition='A human being',
            submitter=self.editor
        )

        custom_field = CustomField.objects.create(
            name='MyCustomField',
            type='int',
            help_text='Custom',
            order=0
        )

        postdata = model_to_dict_with_change_time(object_class)
        postdata[custom_field.form_field_name] = 4

        self.login_editor()
        self.reverse_post(
            'aristotle:edit_item',
            postdata,
            reverse_args=[object_class.id],
            status_code=302
        )
        serialized_data = self.get_serialized_data_dict(object_class)

        self.assertEqual(int(serialized_data['customvalue_set'][0]['content']), 4)

    def test_dss_data_element_inclusion_serialized_through_reversion(self):
        """ Test that DSSDEInclusions added via the concept editor are serialized and saved
         to the DSS's Version"""
        with reversion.create_revision():
            self.dss_de_inclusion.specific_information = 'Highly specific information'
            self.dss_de_inclusion.save()
            self.data_set_specification.save()

        serialized_data = self.get_serialized_data_dict(self.data_set_specification)

        self.assertEqual(serialized_data['dssdeinclusion_set'][0]['specific_information'],
                         'Highly specific information')
