from aristotle_mdr import models
from aristotle_mdr import utils
from aristotle_mdr.utils.versions import VersionField, VersionLinkField
from aristotle_mdr.contrib.reviews.models import ReviewRequest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase, tag


class UtilsTests(TestCase):

    def setUp(self):
        self.steward_org_1 = models.StewardOrganisation.objects.create(name="Test SO")

        self.oc1 = models.ObjectClass.objects.create(
            name='Test OC',
            definition='Test Definition'
        )
        self.oc2 = models.ObjectClass.objects.create(
            name='Test OC2',
            definition='Test Definition2'
        )

    def test_reverse_slugs(self):
        item = models.ObjectClass.objects.create(name=" ",definition="my definition",submitter=None)
        ra = models.RegistrationAuthority.objects.create(name=" ",definition="my definition", stewardship_organisation=self.steward_org_1)
        org = models.Organization.objects.create(name=" ",definition="my definition")
        # wg = models.Workgroup.objects.create(name=" Huh",definition="my definition", stewardship_organisation=self.steward_org_1)

        self.assertTrue('--' in utils.url_slugify_concept(item))
        # Workgroup name cant be space anymore.
        # self.assertTrue('--' in utils.url_slugify_workgroup(wg))
        self.assertTrue('--' in utils.url_slugify_registration_authoritity(ra))
        self.assertTrue('--' in utils.url_slugify_organization(org))

    def test_get_aristotle_url_item(self):
        item = models.ObjectClass.objects.create(name="tname", definition="my definition", submitter=None)
        url = utils.get_aristotle_url(item._meta.label_lower, item.pk, item.name)
        self.assertEqual(url, reverse('aristotle:item', args=[item.pk]))

    def test_get_aristotle_url_ra(self):
        ra = models.RegistrationAuthority.objects.create(name="tname",definition="my definition", stewardship_organisation=self.steward_org_1)
        url = utils.get_aristotle_url(ra._meta.label_lower, ra.pk, ra.name)
        self.assertEqual(url, reverse('aristotle:registrationAuthority', args=[ra.pk, ra.name]))

    def test_get_aristotle_url_org(self):
        org = models.Organization.objects.create(name="tname", definition="my definition")
        url = utils.get_aristotle_url(org._meta.label_lower, org.pk, org.name)
        self.assertEqual(url, reverse('aristotle:organization', args=[org.pk, org.name]))

    def test_get_aristotle_url_wg(self):
        wg = models.Workgroup.objects.create(name="tname",definition="my definition", stewardship_organisation=self.steward_org_1)
        url = utils.get_aristotle_url(wg._meta.label_lower, wg.pk, wg.name)
        self.assertEqual(url, reverse('aristotle:workgroup', args=[wg.pk, wg.name]))

    def test_get_aristotle_url_rr(self):
        user = get_user_model().objects.create(
            email='user@example.com',
            password='verysecure'
        )
        ra = models.RegistrationAuthority.objects.create(name="tname",definition="my definition", stewardship_organisation=self.steward_org_1)
        rr = ReviewRequest.objects.create(registration_authority=ra, requester=user)
        url = utils.get_aristotle_url(rr._meta.label_lower, rr.pk)
        self.assertEqual(url, reverse('aristotle_reviews:review_details', args=[rr.pk]))

    def test_get_aristotle_url_fake(self):
        url = utils.get_aristotle_url('aristotle_mdr.fake_model', 7, 'fake_name')
        self.assertTrue(url is None)

    def test_pretify_camel_case(self):
        pcc = utils.text.pretify_camel_case
        self.assertEqual(pcc('ScopedIdentifier'), 'Scoped Identifier')
        self.assertEqual(pcc('Namespace'), 'Namespace')
        self.assertEqual(pcc('LongerCamelCase'), 'Longer Camel Case')

    def test_strip_tags_link_text(self):
        stripped = utils.utils.strip_tags('My <a href="/url/">Linked</a> Text')
        self.assertEqual(stripped, 'My Linked Text')

    def test_strip_tags_normal_text(self):
        stripped = utils.utils.strip_tags('Some Normal Text')
        self.assertEqual(stripped, 'Some Normal Text')

    def test_truncate_words_required(self):
        text = 'A whole bunch of words'
        trunced = utils.text.truncate_words(text, 3)
        self.assertEqual(trunced, 'A whole bunch...')

    def test_truncate_words_not_required(self):
        text = 'Only some words'
        trunced = utils.text.truncate_words(text, 3)
        self.assertEqual(trunced, text)

    def test_capitalize_words(self):
        cw = utils.text.capitalize_words
        self.assertEqual(cw('some lower case words'), 'Some Lower Case Words')
        self.assertEqual(cw('Mixed case Words'), 'Mixed Case Words')

    @tag('version')
    def test_version_field_value_only(self):
        field = VersionField(
            fname='Value Field',
            value='My Value',
        )

        self.assertFalse(field.is_link)
        self.assertFalse(field.is_group)
        self.assertFalse(field.is_html)

        self.assertEqual(field.heading, 'Value Field')
        self.assertEqual(str(field), 'My Value')

    @tag('version')
    def test_version_field_link(self):
        field = VersionLinkField(
            fname='Linking field',
            identifier=self.oc1.concept.id,
            obj=self.oc1.concept
        )

        self.assertTrue(field.is_link)
        self.assertFalse(field.is_group)
        self.assertFalse(field.is_html)

        self.assertEqual(field.identifier, self.oc1.id)
        self.assertEqual(field.obj_name, self.oc1.name)

    @tag('version')
    def test_version_field_link_to_none(self):
        field = VersionLinkField(
            fname='Linking field',
            identifier=None,
            obj=None
        )

        self.assertEqual(str(field), 'None')
        self.assertEqual(field.identifier, None)

    @tag('version')
    def test_version_field_link_to_item_no_perm(self):
        field = VersionLinkField(
            fname='Linking field',
            identifier=2,
            obj=None
        )

        self.assertEqual(str(field), VersionLinkField.perm_message)
        self.assertEqual(field.identifier, 2)

    def test_get_concept_models(self):
        cm = utils.utils.get_concept_models()
        self.assertTrue(models.DataElement in cm)
        self.assertFalse(models.PermissibleValue in cm)

    def test_get_concept_models_doesnt_return_concept(self):
        cm = utils.utils.get_concept_models()
        self.assertFalse(models._concept in cm)

    def test_format_seconds_under_60(self):
        self.assertEqual(utils.utils.format_seconds(45), '45 seconds')

    def test_format_seconds_above_60(self):
        self.assertEqual(utils.utils.format_seconds(130), '2 minutes, 10 seconds')

    def test_format_seconds_above_3600(self):
        self.assertEqual(utils.utils.format_seconds(3730), '1 hours, 2 minutes, 10 seconds')

    def test_format_seconds_hours_only(self):
        self.assertEqual(utils.utils.format_seconds(7200), '2 hours')


class ManagersTestCase(TestCase):

    def setUp(self):
        oc = models.ObjectClass.objects.create(
            name='Test OC',
            definition='Just a test'
        )
        dec = models.DataElementConcept.objects.create(
            name='Test DEC',
            definition='Just a test',
            objectClass=oc
        )

    def test_with_related(self):
        with self.assertNumQueries(2):
            dec = models.DataElementConcept.objects.filter(name='Test DEC').first()
            dec.objectClass.name

        with self.assertNumQueries(1):
            dec = models.DataElementConcept.objects.filter(
                name='Test DEC'
            ).with_related().first()
            dec.objectClass.name
