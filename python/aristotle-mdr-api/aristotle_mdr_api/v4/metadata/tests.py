from django.urls import reverse
from rest_framework import status
from aristotle_mdr_api.v4.tests import BaseAPITestCase
from aristotle_mdr import models as mdr_models
from aristotle_mdr.contrib.custom_fields.models import CustomField
from aristotle_mdr.required_settings import ARISTOTLE_SETTINGS


class MetadataRedirectionAPITestCase(BaseAPITestCase):

    def setUp(self):
        super().setUp()

        self.item = mdr_models.ObjectClass.objects.create(
            name='Test Concept',
            definition='Concept Definition',
            submitter=self.user,
        )

        self.login_user()

    def test_get_metadata_type_redirection_works_and_matches_uuid_and_type(self):

        response = self.client.get(
            reverse('api_v4:metadata:get_metadata_type_from_uuid', kwargs={"item_uuid": self.item.uuid}),
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(str(self.item.uuid) in response.url.split("/"))
        self.assertTrue(self.item.item_type.model in response.url.split("/"))

    def test_api_serialiser_response_status_is_200_and_fields_are_shown(self):

        response = self.client.get(
            reverse(
                'api_v4:metadata:retrieve_update_metadata_endpoint_{}'.format(self.item.item_type.model),
                kwargs={
                    "item_uuid": self.item.uuid,
                }
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            {"name": self.item.name, "definition": self.item.definition},
            {"name": response.data['name'], "definition": response.data['definition']},
        )


class ListCreateMetadataAPIViewTestCase(BaseAPITestCase):

    def create_value_domain_with_post_request(self):
        post_data = {
            "name": "My new Value Domain",
            "definition": "This is my brand new Value Domain.",
        }

        return self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_valuedomain',
            ),
            post_data,
            format='json',
        )

    def setUp(self):
        super().setUp()

        from aristotle_dse.models import DataSetSpecification, Dataset
        from aristotle_mdr.contrib.identifiers.models import Namespace
        from comet.models import QualityStatement

        self.value_domain_1 = mdr_models.ValueDomain.objects.create(
            name='Test Value Domain 1',
            definition='VD Definition',
            submitter=self.user,
        )

        self.value_domain_2 = mdr_models.ValueDomain.objects.create(
            name='Test Value Domain 2',
            definition='VD Definition',
            submitter=self.user,
        )

        self.custom_field_1 = CustomField.objects.create(
            name="Test CustomField",
            order=1,
        )

        self.custom_field_2 = CustomField.objects.create(
            name="Test CustomField",
            order=2,
        )

        self.de1 = mdr_models.DataElement.objects.create(
            name="My DE 1",
            definition="My Def 1",
            workgroup=self.wg,
        )

        self.de2 = mdr_models.DataElement.objects.create(
            name="My DE 2",
            definition="My Def 2",
            workgroup=self.wg,
        )

        self.oc = mdr_models.ObjectClass.objects.create(
            name='Test Object Class',
            definition='Test Defn',
            workgroup=self.wg
        )

        self.dss = DataSetSpecification.objects.create(
            name="My DSS",
            definition="My definition",
        )

        self.qs = QualityStatement.objects.create(
            name="My Test QS",
            definition="My QS definition.",
        )

        self.ds = Dataset.objects.create(
            name="My DS",
            definition="MY DS definition."
        )

        self.org_record = mdr_models.OrganizationRecord.objects.create(
            stewardship_organisation=self.so,
        )

        self.namespace = Namespace.objects.create(
            shorthand_prefix="Hello world",
            stewardship_organisation=self.so,
        )

        self.login_user()

    def test_api_list_or_create_metadata_get_request(self):

        response = self.client.get(
            reverse('api_v4:metadata:list_or_create_metadata_endpoint_valuedomain'), data={"page": 1, "page_size": 2}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Make sure response is OK.
        self.assertEqual(len(response.data['results']), 2)  # Make sure the length is correct.
        self.assertEqual(response.data['count'], 2)  # Make sure the length is correct.
        self.assertIsNone(response.data['next'])  # Make sure the paginator works.
        self.assertIsNone(response.data['previous'])  # Make sure the paginator works.

    def test_api_list_or_create_metadata_post_request_cannot_be_made_by_anonymous_users(self):

        self.logout()

        response = self.create_value_domain_with_post_request()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.login_user()

    def test_api_list_or_create_metadata_post_request_actually_creates_metadata_and_submitter_is_correct(self):

        response = self.create_value_domain_with_post_request()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.user, mdr_models.ValueDomain.objects.last().submitter)

    def test_reversion_object_created_during_update_api_calls_with_put_request(self):

        self.create_value_domain_with_post_request()

        from reversion.models import Revision
        last_revision = Revision.objects.last()

        self.assertEqual(
            last_revision.comment,
            "Added via {} API.".format(ARISTOTLE_SETTINGS['SITE_NAME'])
        )
        self.assertEqual(last_revision.user, self.user)

    def test_api_list_or_create_metadata_post_request_cannot_accept_ids_or_pks_inside_subcomponents(self):

        sv_1 = mdr_models.SupplementaryValue.objects.create(
            value="I am supplementary value # 1",
            meaning="I belong to VD #1",
            valueDomain=self.value_domain_1,
            order=0
        )

        post_data = {
            "name": "My VD with Supplementary Values with ids.",
            "definition": "I am trying to steal Supplementary Values from another VD, be careful...",
            "workgroup": self.wg.id,
            "supplementaryvalue_set": [
                {
                    "value": "hello",
                    "order": 0,
                    "id": sv_1.id,  # We don't allow ids.
                },
            ],
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_valuedomain',
            ),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        post_data = {
            "name": "My VD with Supplementary Values with ids.",
            "definition": "I am trying to steal Supplementary Values from another VD, be careful...",
            "workgroup": self.wg.id,
            "supplementaryvalue_set": [
                {
                    "value": "hello",
                    "order": 0,
                    "pk": sv_1.id,  # We don't allow pks.
                },
            ],
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_valuedomain',
            ),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_list_or_create_metadata_post_request_with_foreign_keys(self):

        post_data = {
            "name": "MY TEST DATA ELEMENT",
            "definition": "DEFINITION FOR MY TEST DATA ELEMENT",
            "origin": "Blah blah...",
            "valueDomain": str(self.value_domain_1.uuid),
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_dataelement',
            ),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(self.value_domain_1.uuid), response.data['valueDomain'])
        self.assertEqual(post_data['name'], mdr_models.DataElement.objects.last().name)  # Data Element is in db.

    def test_api_list_or_create_metadata_post_request_with_incorrect_uuid(self):

        post_data = {
            "name": "MY TEST DATA ELEMENT",
            "definition": "DEFINITION FOR MY TEST DATA ELEMENT",
            "valueDomain": "e39a9a05-a1f6-4035-8d67-a8334825b735",  # This is an incorrect UUID.
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_dataelement',
            ),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_list_or_create_metadata_post_request_for_data_element_with_subcomponents(self):

        post_data = {
            "name": "MY DATA ELEMENT WITH CUSTOM VALUES",
            "definition": "THIS DATA ELEMENT HAS CUSTOM VALUES.",
            "workgroup": self.wg.id,
            "customvalue_set": [
                {
                    "content": "hello",
                    "field": self.custom_field_1.id,
                },
                {
                    "content": "HELLO 2",
                    "field": self.custom_field_2.id,
                },
            ],
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_dataelement',
            ),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Make sure we actually created data.
        self.assertEqual(len(response.data['customvalue_set']), 2)  # Make sure we have 2 custom value objects.
        self.assertEqual(response.data['workgroup'], self.wg.id)  # Workgroup was actually saved.
        self.assertEqual(post_data['name'], mdr_models.DataElement.objects.last().name)  # Data Element is in db.

    def test_api_list_or_create_metadata_post_request_for_value_domain_with_subcomponents(self):

        dt = mdr_models.DataType.objects.create(name="Test DT", workgroup=self.wg)

        post_data = {
            "name": "My Value Domain",
            "definition": "My Value Domain definition",
            "stewardship_organisation": self.so.uuid,
            "workgroup": self.wg.id,
            "submitter": None,
            "version": "",
            "references": "These are my references",
            "origin_URI": "",
            "origin": "This is my origin",
            "comments": "My comments",
            "data_type": dt.uuid,
            "format": "N",
            "maximum_length": 1,
            # "unit_of_measure": None,  # TODO: FIX THIS!
            # "conceptual_domain": None,
            "description": "",
            "permissiblevalue_set": [
                {
                    "value": "0",
                    "meaning": "My meaning",
                    "order": 1,
                    "start_date": "2018-01-01",
                },
                {
                    "value": "1",
                    "meaning": "My meaning 1",
                    "order": 2,
                    "start_date": "2018-02-02",
                },
            ],
            "supplementaryvalue_set": [
                {
                    "value": "s0",
                    "meaning": "My meaning sv",
                    "order": 1,
                    "start_date": "2018-01-01",
                },
                {
                    "value": "s1",
                    "meaning": "My meaning sv 1",
                    "order": 2,
                    "start_date": "2018-02-02",
                }
            ],
            "slots": [],
            "customvalue_set": [
                {
                    "field": self.custom_field_1.id,
                    "name": "New Name 1",
                    "content": "Activity - need for assistance",
                },
                {
                    "field": self.custom_field_2.id,
                    "name": "New Name 2",
                    "content": "",
                },
            ],
            "org_records": [],
            "identifiers": []
        }

        response = self.client.post(
            reverse(
                'api_v4:metadata:list_or_create_metadata_endpoint_valuedomain',
            ),
            post_data,
            format='json',
        )

        last_vd = mdr_models.ValueDomain.objects.last()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Make sure we actually created data.
        self.assertEqual(len(response.data['supplementaryvalue_set']), 2)  # We have 2 supplementary value objects.
        self.assertEqual(len(response.data['permissiblevalue_set']), 2)  # We have 2 permissible value objects.
        self.assertEqual(response.data['data_type'], str(dt.uuid))  # The DataType was actually saved.
        self.assertEqual(post_data['name'], last_vd.name)  # ValueDomain is in db.
        self.assertEqual(post_data['permissiblevalue_set'][0]['value'], last_vd.permissibleValues[0].value)
        self.assertEqual(post_data['permissiblevalue_set'][0]['meaning'], last_vd.permissibleValues[0].meaning)
        self.assertEqual(post_data['permissiblevalue_set'][0]['order'], last_vd.permissibleValues[0].order)
        self.assertEqual(post_data['permissiblevalue_set'][1]['value'], last_vd.permissibleValues[1].value)
        self.assertEqual(post_data['permissiblevalue_set'][1]['meaning'], last_vd.permissibleValues[1].meaning)
        self.assertEqual(post_data['permissiblevalue_set'][1]['order'], last_vd.permissibleValues[1].order)

    def test_api_list_or_create_metadata_post_request_for_data_set_specification_with_subcomponents(self):

        from aristotle_dse.models import DataSetSpecification

        post_data = {
            "name": "Test DSS",
            "definition": "This is my definition",
            "stewardship_organisation": None,
            "submitter": None,
            "version": "",
            "references": "",
            "origin_URI": "",
            "origin": "",
            "comments": "",
            # "statistical_unit": None,  WE NEED TO IMPLEMENT A TEST WITH STATISTICAL UNITS.
            "collection_method": "My collection method.",
            "groups": [],
            "dssdeinclusion_set": [
                {
                    "reference": "1",
                    "maximum_occurrences": 18,
                    "inclusion": "mandatory",
                    "specific_information": "This is my specific info.",
                    "conditional_inclusion": "Conditional inclusion",
                    "order": 0,
                    "data_element": self.de1.id,
                    "group": None,
                    "specialisation_classes": [
                        self.oc.id,
                    ]
                },
                {
                    "reference": "2",
                    "maximum_occurrences": 1,
                    "inclusion": "conditional",
                    "specific_information": "Specific info",
                    "conditional_inclusion": "My conditional inclusion.",
                    "order": 1,
                    "data_element": self.de2.id,
                    "group": None,
                    "specialisation_classes": [
                        self.oc.id,
                    ]
                },
            ],
            "dssclusterinclusion_set": [
                {
                    "reference": "",
                    "maximum_occurrences": 99,
                    "inclusion": "conditional",
                    "specific_information": "",
                    "conditional_inclusion": "Conditional Incl",
                    "order": 2,
                    "child": self.dss.id
                }
            ],
            "slots": [],
            "customvalue_set": [
                {
                    "field": self.custom_field_1.id,
                    "name": "New Name 1",
                    "content": "Activity - need for assistance",
                },
                {
                    "field": self.custom_field_2.id,
                    "name": "New Name 2",
                    "content": "",
                },
            ],
            "org_records": [],
            "identifiers": [],
        }

        response = self.client.post(
            reverse('api_v4:metadata:list_or_create_metadata_endpoint_datasetspecification'),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Make sure we actually created data.
        self.assertEqual(len(response.data['dssdeinclusion_set']), 2)  # We have 2 dss de inclusion objects.
        self.assertEqual(len(response.data['dssclusterinclusion_set']), 1)  # We have 1 dss cluster inclusion objects.
        self.assertEqual(len(response.data['customvalue_set']), 2)  # We have 2 custom value objects.
        self.assertEqual(post_data['name'], DataSetSpecification.objects.last().name)  # DSS is in db.

    def test_api_list_or_create_metadata_post_request_for_indicator_with_subcomponents(self):

        post_data = {
            "name": "my Test Indicator",
            "definition": "This is my Indicator Definition.",
            "workgroup": self.wg.id,
            "version": "v 1.1.0",
            "references": "My references",
            "origin_URI": "https://duckduckgo.com/",
            "origin": "my origin",
            "comments": "my comments",
            "computation_description": "my computation description.",
            "computation": "my computation.",
            "numerator_description": "This is the description of my Numerator.",
            "denominator_description": "This is the description of my denominator.",
            "disaggregation_description": "This is the disaggregation.",
            "quality_statement": self.qs.uuid,
            "rationale": "My rationale",
            "benchmark": "My benchmark",
            "reporting_information": "My reporting information.",
            "indicatornumeratordefinition_set": [
                {
                    "order": 0,
                    "guide_for_use": "Guide for use 1",
                    "description": "Description of guide for use.",
                    "data_element": self.de1.id,
                    "data_set_specification": self.dss.id,
                    "data_set": self.ds.id,
                }
            ],
            "indicatordenominatordefinition_set": [
                {
                    "order": 0,
                    "guide_for_use": "Guide for use 2",
                    "description": "Description",
                    "data_element": self.de1.id,
                    "data_set_specification": self.dss.id,
                    "data_set": self.ds.id,
                }
            ],
            "indicatordisaggregationdefinition_set": [
                {
                    "order": 0,
                    "guide_for_use": "Guide for use.",
                    "description": "Description.",
                    "data_element": self.de2.id,
                    "data_set_specification": self.dss.id,
                    "data_set": self.ds.id,
                }
            ],
            "slots": [
                {
                    "name": "Test slot",
                    "value": "value",
                    "order": 0,
                    "permission": 0
                }
            ],
            "customvalue_set": [
                {
                    "field": self.custom_field_1.id,
                    "content": "string"
                }
            ],
            "org_records": [
                {
                    "organization_record": self.org_record.id,
                    "type": "s"
                }
            ],
            "identifiers": [
                {
                    "namespace": self.namespace.id,
                    "identifier": "string",
                    "version": "string",
                    "order": 0
                }
            ]
        }

        response = self.client.post(
            reverse('api_v4:metadata:list_or_create_metadata_endpoint_indicator'),
            post_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Make sure we actually created data.


class UpdateMetadataAPIViewTestCase(BaseAPITestCase):

    def setUp(self):

        super().setUp()

        self.login_superuser()

        self.de = mdr_models.DataElement.objects.create(
            name="Test Data Element",
            definition="This is my Test DE!",
            version="version 1.0",
            submitter=self.user
        )

        self.vd_1 = mdr_models.ValueDomain.objects.create(
            name="I am VD # 1",
            definition="I have my own Supplementary Value. It is only mine!"
        )

        self.vd_2 = mdr_models.ValueDomain.objects.create(
            name="I am VD # 2",
            definition="I have my own Supplementary Value."
        )

        self.sv_1 = mdr_models.SupplementaryValue.objects.create(
            value="I am supplementary value # 1",
            meaning="I belong to VD #1",
            valueDomain=self.vd_1,
            order=0
        )

        self.sv_2 = mdr_models.SupplementaryValue.objects.create(
            value="I am supplementary value # 2",
            meaning="I belong to VD #2",
            valueDomain=self.vd_2,
            order=5
        )

    def test_update_data_element_with_put_request(self):

        put_data = {
            "name": "My test DE",
            "definition": "Yeah!",
            "workgroup": self.wg.id,
            "references": "string",
            "origin_URI": "https://duckduckgo.com/",
            "origin": "string",
            "comments": "string",
            "slots": [
                {
                    "name": "The cool slot name",
                    "value": "Yay!",
                    "order": 0,
                    "permission": 0
                }
            ]
        }

        response = self.client.put(
            reverse(
                'api_v4:metadata:retrieve_update_metadata_endpoint_dataelement',
                kwargs={"item_uuid": self.de.uuid}
            ),
            put_data,
            format='json',
        )

        self.de.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Make sure we actually changed the data.
        self.assertEqual(self.de.id, response.data['id'])  # Make sure both objects have the same id.
        self.assertEqual(self.de.version, response.data['version'])  # We didn't change the version.
        self.assertEqual(self.de.name, response.data['name'])
        self.assertEqual(self.de.definition, response.data['definition'])
        self.assertEqual(self.de.workgroup.id, response.data['workgroup'])
        self.assertEqual(self.de.origin_URI, response.data['origin_URI'])
        self.assertEqual(self.de.name, response.data['name'])
        self.assertEqual(self.de.slots.all().count(), 1)  # Slot was created.
        self.assertEqual(self.de.slots.all()[0].name, response.data['slots'][0]['name'])
        self.assertEqual(self.de.slots.all()[0].value, response.data['slots'][0]['value'])

    def test_update_data_element_with_patch_request(self):

        patch_data = {
            "name": "My new name",
        }

        response = self.client.patch(
            reverse('api_v4:metadata:retrieve_update_metadata_endpoint_dataelement',
                    kwargs={"item_uuid": self.de.uuid}),
            patch_data,
            format='json',
        )

        self.de.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Make sure we actually changed the data.
        self.assertEqual(self.de.name, response.data['name'])

    def test_sub_items_in_json_data_can_update_actual_items_when_their_id_is_provided(self):

        patch_data = {
            "name": "My new vd name",
            "supplementaryvalue_set": [
                {
                    "value": "Yeah SV!",
                    "order": 5,
                    "id": self.sv_1.id,
                }
            ]
        }

        response = self.client.patch(
            reverse('api_v4:metadata:retrieve_update_metadata_endpoint_valuedomain',
                    kwargs={"item_uuid": self.vd_1.uuid}),
            patch_data,
            format='json',
        )

        self.de.refresh_from_db()
        self.sv_1.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Make sure we actually changed the data.
        self.assertEqual(self.sv_1.id, response.data['supplementaryvalue_set'][0]['id'])
        self.assertEqual(self.sv_1.value, response.data['supplementaryvalue_set'][0]['value'])
        self.assertEqual(self.sv_1.order, response.data['supplementaryvalue_set'][0]['order'])

    def test_avoid_updating_sub_items_that_are_not_linked_to_the_parent_item(self):

        patch_data = {
            "supplementaryvalue_set": [
                {
                    "id": self.sv_2.id,
                    "meaning": "Oh no, please don't move me to VD # 1!",
                }
            ]
        }

        response = self.client.patch(
            reverse('api_v4:metadata:retrieve_update_metadata_endpoint_valuedomain',
                    kwargs={"item_uuid": self.vd_1.uuid}),
            patch_data,
            format='json',
        )

        self.vd_1.refresh_from_db()
        self.vd_2.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # Make sure we actually get an error.
        self.assertEqual(self.vd_1.supplementaryvalue_set.all()[0].id, self.sv_1.id)
        self.assertEqual(self.vd_2.supplementaryvalue_set.all()[0].id, self.sv_2.id)

    def test_update_subitems_with_empty_list(self):
        patch_data = {
            "supplementaryvalue_set": []
        }

        response = self.client.patch(
            reverse('api_v4:metadata:retrieve_update_metadata_endpoint_valuedomain',
                    kwargs={"item_uuid": self.vd_1.uuid}),
            patch_data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Make sure we actually changed the data.
        self.assertCountEqual(self.vd_1.supplementaryvalue_set.all(), [])  # The list should be empty.
        self.assertFalse(self.vd_1.supplementaryvalue_set.all())

    def test_reversion_object_created_during_update_api_calls_with_put_request(self):

        put_data = {
            "name": "My updated TEST DE",
            "definition": "Yeah 222!",
            "workgroup": self.wg.id,
            "references": "This has been changed",
            "origin_URI": "https://duckduckgo.com/",
            "origin": "string",
            "comments": "string",
            "slots": [
                {
                    "name": "The cool slot name",
                    "value": "Yay!",
                    "order": 0,
                    "permission": 0
                }
            ]
        }

        self.client.put(
            reverse(
                'api_v4:metadata:retrieve_update_metadata_endpoint_dataelement',
                kwargs={"item_uuid": self.de.uuid}
            ),
            put_data,
            format='json',
        )

        from reversion.models import Revision
        last_revision = Revision.objects.last()

        self.assertEqual(
            last_revision.comment,
            'Changed name, definition, workgroup, references, origin URI, origin, comments and slot.'
        )
        self.assertEqual(last_revision.user, self.su)
