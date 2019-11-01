from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from aristotle_mdr import models as mdr_models
from aristotle_mdr_api.v4.tests import BaseAPITestCase
from aristotle_mdr.contrib.publishing.models import VersionPermissions
from aristotle_mdr.constants import visibility_permission_choices as VISIBILITY_PERMISSION_CHOICES

import reversion
from reversion.models import Version

import logging

logger = logging.getLogger(__name__)


class ConceptAPITestCase(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.item = mdr_models.ObjectClass.objects.create(
            name='Test Concept',
            definition='Concept Definition',
            submitter=self.user
        )
        self.concept = self.item._concept_ptr

        self.public_concept = mdr_models.ObjectClass.objects.create(
            name='Public',
            definition="Public Definition",
            submitter=self.user

        )

        self.non_public_concept = mdr_models.ObjectClass.objects.create(
            name='Not Public',
            definition='Not a Public Definition',
            submitter=self.user
        )

        self.so = mdr_models.StewardOrganisation.objects.create(
            name='Best Stewardship Organisation',
        )

        self.ra = mdr_models.RegistrationAuthority.objects.create(
            name='First RA',
            definition='First',
            stewardship_organisation=self.so
        )
        # Make the public_concept public
        self.status  = mdr_models.Status.objects.create(
            concept=self.public_concept,
            registrationAuthority=self.ra,
            registrationDate=timezone.now(),
            state=self.ra.public_state
        )

        # Create a new item without version permissions
        with reversion.revisions.create_revision():
            self.reversion_item_without_permissions = mdr_models.ObjectClass.objects.create(
                name="A concept without permissions",
                definition="Concept with no permissions",
                submitter=self.user
            )
            reversion.revisions.set_comment("First edit")

        # Create a new item with version permissions
        with reversion.revisions.create_revision():
            self.reversion_item_with_permissions = mdr_models.ObjectClass.objects.create(
                name="A published item",
                definition="Concept with no permissions",
                submitter=self.user
            )
        self.version_without_permission = Version.objects.get_for_object(
            self.reversion_item_without_permissions).first()

        self.version_with_permission = Version.objects.get_for_object(self.reversion_item_with_permissions).first()
        VersionPermissions.objects.create(version=self.version_with_permission)

    def test_get_concept(self):
        self.login_user()
        response = self.client.get(
            reverse('api_v4:item:item', args=[self.concept.id]),
        )
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_can_view_public_concept(self):
        response = self.client.get(
                reverse('api_v4:item:item', args=[self.public_concept.id]),
            )

        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_cant_view_non_public_concept(self):
        response = self.client.get(
            reverse('api_v4:item:item', args=[self.non_public_concept.id]),
        )

        self.assertEqual(response.status_code, 401)

    def test_unauth_user_can_view_graph_representation_public_concept(self):
        response = self.client.get(
            reverse('api_v4:item:item_general_graphical', args=[self.public_concept.id]),
        )

        self.assertEqual(response.status_code, 200)

    def test_unauth_user_cant_view_graph_representation_non_public_concept(self):

        response = self.client.get(
            reverse('api_v4:item:item_general_graphical', args=[self.non_public_concept.id]),
        )

        self.assertEqual(response.status_code, 403)

    def test_unauth_user_can_view_links_representation_public_concept(self):
        response = self.client.get(
            reverse('api_v4:item:api_item_links', args=[self.public_concept.id]),
        )
        self.assertEqual(response.status_code, 200)

    def test_unauth_user_cant_view_links_representation_non_public_concept(self):
        response = self.client.get(
            reverse('api_v4:item:api_item_links', args=[self.non_public_concept.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_supersedes_graph(self):
        self.steward_org_1 = mdr_models.StewardOrganisation.objects.create(
            name="Test SO"
        )
        self.superseded_item = mdr_models.DataElementConcept.objects.create(
            name="SUPERSEDED ITEM",
            submitter=self.user
        )

        self.superseding_item = mdr_models.DataElementConcept.objects.create(
            name="SUPERSEDING ITEM",
            submitter=self.user
        )
        self.ra = mdr_models.RegistrationAuthority.objects.create(
            name="Test RA",
            stewardship_organisation=self.steward_org_1
        )

        mdr_models.SupersedeRelationship.objects.create(
            older_item=self.superseded_item,
            newer_item=self.superseding_item,
            registration_authority=self.ra
        )

        self.login_user()
        response = self.client.get(
            reverse('api_v4:item:item_supersedes_graphical', args=[self.superseded_item.id])
        )
        self.assertEqual(len(response.data['nodes']), 2)
        self.assertEqual(len(response.data['edges']), 1)

    def test_general_graph_number_of_nodes(self):
        self.maximum_number_of_nodes = settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION

        for i in range(settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION):
            mdr_models.DataElementConcept.objects.create(
                name="TEST DATA ELEMENT CONCEPT",
                definition="I like to be with the popular Concept",
                objectClass=self.item,
                submitter=self.user,
            )

        self.assertEqual(len(mdr_models.DataElementConcept.objects.all()),
                         settings.MAXIMUM_NUMBER_OF_NODES_IN_GENERAL_GRAPHICAL_REPRESENTATION)

        self.login_user()
        response = self.client.get(
            reverse('api_v4:item:item_general_graphical', args=[self.item.id])
        )

        self.assertEqual(len(response.data['nodes']), self.maximum_number_of_nodes)
        self.assertEqual(len(response.data['edges']), self.maximum_number_of_nodes - 1)

        # Create an extra DataElementConcept attached to the same item
        mdr_models.DataElementConcept.objects.create(
            name="TEST DATA ELEMENT CONCEPT",
            definition="I like to be with the popular Concept",
            objectClass=self.item,
            submitter=self.user,
        )

        response2 = self.client.get(
            reverse('api_v4:item:item_general_graphical', args=[self.item.id])
        )
        # The number of nodes and edges has to remain the same:
        self.assertEqual(len(response2.data['nodes']), self.maximum_number_of_nodes)
        self.assertEqual(len(response2.data['edges']), self.maximum_number_of_nodes - 1)

    def test_unauthenticated_user_cant_update_version_permissions(self):
        self.login_other_user()

        post_data = [{
            "version_id": self.version_with_permission.id,
            "visibility": 2
        }]

        response = self.client.post(
            reverse('api_v4:item:update-version-permissions', args=[self.reversion_item_with_permissions.id]),
            post_data, format='json')

        self.assertEqual(response.status_code, 403)

    def test_api_updates_version_permissions(self):
        self.login_user()

        post_data = [{
            "version_id": self.version_with_permission.id,
            "visibility": 0,
        }]
        response = self.client.post(
            reverse('api_v4:item:update-version-permissions', args=[self.reversion_item_with_permissions.id]),
            post_data, format='json')

        self.assertEqual(response.status_code, 200)

        self.assertCountEqual(response.data, post_data, "The response should be the same as the posted data")

        self.assertEqual(
            int(VersionPermissions.objects.get_object_or_none(version=self.version_with_permission).visibility),
            0)

    def test_user_not_in_workgroup_cant_update_version_permissions(self):
        self.login_other_user()

        post_data = [{
            "version_id": self.version_with_permission.id,
            "visibility": VISIBILITY_PERMISSION_CHOICES.public,
        }]

        response = self.client.post(
            reverse('api_v4:item:update-version-permissions', args=[self.reversion_item_with_permissions.id]),
            post_data, format='json')

        self.assertEqual(response.status_code, 403)

    def test_api_can_create_version_permissions(self):
        self.login_user()

        post_data = [{
            "version_id": self.version_without_permission.id,
            "visibility": VISIBILITY_PERMISSION_CHOICES.workgroup,
        }]

        response = self.client.post(
            reverse('api_v4:item:update-version-permissions', args=[self.reversion_item_without_permissions.id]),
            post_data, format='json'
        )

        self.assertEqual(response.status_code, 200)

        self.assertCountEqual(response.data, post_data, "The response should be the same as the posted data")

        self.assertEqual(
            VersionPermissions.objects.get_object_or_none(version=self.version_without_permission).visibility,
            VISIBILITY_PERMISSION_CHOICES.workgroup)

    def test_api_cant_edit_non_item_version_permissions(self):
        self.login_user()

        post_data = [
            {"version_id": self.version_with_permission.id,
             "visibility": VISIBILITY_PERMISSION_CHOICES.public},
            {"version_id": self.version_without_permission.id,
             "visibility": VISIBILITY_PERMISSION_CHOICES.workgroup}
        ]

        response = self.client.post(
            reverse('api_v4:item:update-version-permissions', args=[self.reversion_item_with_permissions.id]),
            post_data, format='json'
        )

        self.assertEqual(response.status_code, 400)

        # Assert that no visibility object was created in the database

        self.assertIsNone(VersionPermissions.objects.get_object_or_none(version=self.version_without_permission))

        # Check that the other version permissions were not updated
        self.assertEqual(VersionPermissions.objects.get_object_or_none
                             (version=self.version_with_permission).visibility,
                         VISIBILITY_PERMISSION_CHOICES.workgroup)
