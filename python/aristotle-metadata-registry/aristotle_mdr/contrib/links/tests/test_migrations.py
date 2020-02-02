from django.test import TestCase
from aristotle_mdr.tests.migration_test_utils import MigrationsTestCase


class UUIDToPrimaryKeyTestBaseForLinkEnd(MigrationsTestCase, TestCase):
    app = 'aristotle_mdr_links'

    def setUpBeforeMigration(self, apps):
        self.Link = apps.get_model('aristotle_mdr_links', 'link')
        self.LinkEnd = apps.get_model('aristotle_mdr_links', 'linkend')
        self.Relation = apps.get_model('aristotle_mdr_links', 'relation')
        self.RelationRole = apps.get_model('aristotle_mdr_links', 'relationrole')
        self.DataElement = apps.get_model('aristotle_mdr', 'dataelement')

        self.de1 = self.DataElement.objects.create(name="Test DE 1", definition="definition")
        self.de2 = self.DataElement.objects.create(name="Test DE 2", definition="definition")

        self.rel = self.Relation.objects.create(name="test_relation", definition="Used for testing")
        self.rel_role = self.RelationRole.objects.create(
            name="Relation Role Test", definition="test role", multiplicity=1,
            ordinal=2,
            relation=self.rel
        )
        self.link = self.Link.objects.create(relation=self.rel, root_item=self.de1)


class TestRelationRolePrimaryKeyChange(UUIDToPrimaryKeyTestBaseForLinkEnd):

    migrate_from = '0013_add_temp_field'
    migrate_to = '0014_copy_and_paste_foreign_value'

    def setUpBeforeMigration(self, apps):
        super().setUpBeforeMigration(apps)

        self.LinkEnd.objects.create(link=self.link, role=self.rel_role, concept=self.de2)
        # Make sure the temporary field is a UUID field:
        self.assertEqual(self.LinkEnd._meta.get_field('role_temp').get_internal_type(), 'UUIDField')
        # Make sure the LinkEnd object has a role assigned to it:
        le = self.LinkEnd.objects.last()
        self.assertEqual(le.role, self.rel_role)

    def test_migration(self):
        LinkEnd = self.apps.get_model('aristotle_mdr_links', 'linkend')
        RelationRole = self.apps.get_model('aristotle_mdr_links', 'relationrole')
        le = LinkEnd.objects.last()
        relation_role = RelationRole.objects.last()
        # Make sure the temporary uuid field has the value of the foreign key field:
        self.assertEqual(le.role_temp, relation_role.uuid)


class TestRelationRoleUUIDForeignKey(UUIDToPrimaryKeyTestBaseForLinkEnd):

    migrate_from = '0016_add_foreign_key_field'
    migrate_to = '0017_copy_and_paste_to_foreign_key'

    def setUpBeforeMigration(self, apps):
        super().setUpBeforeMigration(apps)

        self.LinkEnd.objects.create(link=self.link, role_temp=self.rel_role.uuid, concept=self.de2)
        # Make sure the new Field is a Foreign Key field:
        self.assertEqual(self.LinkEnd._meta.get_field('role').get_internal_type(), 'ForeignKey')

    def test_migration(self):
        LinkEnd = self.apps.get_model('aristotle_mdr_links', 'linkend')
        RelationRole = self.apps.get_model('aristotle_mdr_links', 'relationrole')
        le = LinkEnd.objects.last()
        relation_role = RelationRole.objects.last()

        self.assertEqual(le.role, relation_role)   # Check that new foreign key is working.
        self.assertTrue(LinkEnd._meta.get_field('role').is_relation)  # The new field is a foreign key (relation) field.
        self.assertEqual(le.role.uuid, relation_role.uuid)
