from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

import datetime


from aristotle_mdr import models as MDR
from aristotle_mdr.contrib.validators import validators
from aristotle_mdr.contrib.validators import models
from aristotle_mdr.contrib.validators import runners
from aristotle_mdr.contrib.reviews.models import ReviewRequest


class ValidationTester(TestCase):
    def assertValid(self, result, expected_message=""):
        is_valid, actual_message = result
        self.assertTrue(is_valid)
        self.assertEqual(actual_message, expected_message)

    def assertNotValid(self, result, expected_message=""):
        is_valid, actual_message = result
        self.assertFalse(is_valid)
        self.assertEqual(actual_message, expected_message)


class TestBaseValidator(ValidationTester):
    def test_validator_name(self):

        validator = validators.BaseValidator({
            'name': 'TestName'
        })

        self.assertEqual(validator.get_name(), 'TestName')

        validator = validators.BaseValidator({
            'validator': 'RegexValidator'
        })

        self.assertEqual(validator.get_name(), 'Unnamed RegexValidator')


class TestRegexValidator(ValidationTester):
    def test_invalid_rule(self):
        self.assertNotValid(
            validators.RegexValidator(
                rule={}
            ).validate(None),
            expected_message="Invalid rule"
        )

    def test_validator(self):
        employ = MDR.ValueDomain.objects.create(name="employment Statuses", definition=".")
        rule = {'regex': '[A-Z].+', 'field': 'name'}

        self.assertNotValid(
            validators.RegexValidator(
                rule=rule
            ).validate(employ),
            expected_message="Text '{}' does not match required pattern.".format(employ.name)
        )

        employ.name = "Employment Status"
        employ.save()
        self.assertValid(
            validators.RegexValidator(rule=rule).validate(employ),
        )

    def test_regex_validator(self):
        self.item = MDR.ObjectClass(
            name='Test Object Class',
            definition=''
        )

        # Test validator for 4 length word
        validator = validators.RegexValidator({
            'name': 'regex',
            'field': 'name',
            'regex': r'\w{4}'
        })

        self.item.name = 'yeah'
        self.assertTrue(validator.validate(self.item)[0])

        self.item.name = 'yea'
        self.assertFalse(validator.validate(self.item)[0])

        self.item.name = 'yeahh'
        self.assertFalse(validator.validate(self.item)[0])


class TestRelationValidator(ValidationTester):
    def test_invalid_rule(self):
        person_age = MDR.DataElementConcept.objects.create(name="Person-Age", definition=".")
        rule = {'field': 'name'}

        self.assertNotValid(
            validators.RelationValidator(
                rule=rule
            ).validate(person_age),
            expected_message=validators.RelationValidator.errors['NOT_FK'].format('name')
        )
        rule = {'field': 'fake_field'}

        self.assertNotValid(
            validators.RelationValidator(
                rule=rule
            ).validate(person_age),
            expected_message=validators.RelationValidator.errors['NOT_FOUND'].format('fake_field')
        )

    def test_validator(self):
        person = MDR.ObjectClass.objects.create(name="Person", definition=".")
        person_age = MDR.DataElementConcept.objects.create(name="Person-Age", definition=".")
        rule = {'field': 'property'}

        self.assertNotValid(
            validators.RelationValidator(
                rule=rule
            ).validate(person_age),
            expected_message=validators.RelationValidator.errors['NOT_LINKED'].format("property")
        )

        age = MDR.Property.objects.create(name="Age", definition=".")
        person_age.property = age
        self.assertValid(
            validators.RelationValidator(rule=rule).validate(person_age),
        )


class TestUniqueValuesValidator(ValidationTester):

    def test_validator(self):
        employ = MDR.ValueDomain.objects.create(name="Employment Statuses", definition=".")
        a = MDR.PermissibleValue.objects.create(valueDomain=employ, value="e", meaning="Employed", order=1)
        b = MDR.PermissibleValue.objects.create(valueDomain=employ, value="u", meaning="Unemployed", order=2)
        c = MDR.PermissibleValue.objects.create(valueDomain=employ, value="u", meaning="Underemployed", order=3)

        self.assertNotValid(
            validators.UniqueValuesValidator(rule={}).validate(employ),
            expected_message="Value 'u' is a permissible value more than once - it appeared 2 times"
        )

        c.value="under"
        c.save()
        self.assertValid(
            validators.UniqueValuesValidator(rule={}).validate(employ),
        )


class TestStatusValidator(ValidationTester):

    def setUp(self):
        self.steward_org_1 = MDR.StewardOrganisation.objects.create(
            name='Org 1',
            description="1",
        )
        self.item = MDR.ObjectClass.objects.create(
            name='Test Object Class',
            definition='Test Defn'
        )
        self.ra = MDR.RegistrationAuthority.objects.create(
            name='Test Content',
            definition='Only test content',
            stewardship_organisation=self.steward_org_1
        )

    def register_item_standard(self):
        # Register the item on 2 seperate dates to check that only most recent
        # is used
        MDR.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2014, 1, 1),
            state=MDR.STATES.incomplete
        )
        MDR.Status.objects.create(
            concept=self.item,
            registrationAuthority=self.ra,
            effective_date=datetime.date(2014, 1, 2),
            state=MDR.STATES.standard
        )

    def test_status_validation_pass(self):
        self.register_item_standard()

        validator = validators.StatusValidator({
            'name': 'standard check',
            'status': ['Standard', 'Retired'],
        })

        self.assertValid(
            validator.validate(self.item, self.ra),
            expected_message='Valid State'
        )

    def test_status_validation_fail(self):
        self.register_item_standard()

        validator = validators.StatusValidator({
            'name': 'standard check',
            'status': ['NotProgressed', 'Incomplete'],
        })

        self.assertNotValid(
            validator.validate(self.item, self.ra),
            expected_message='Invalid State'
        )

    def test_status_validation_bad_state(self):
        # Test with an invalid state
        validator = validators.StatusValidator({
            'name': 'standard check',
            'status': ['MuchoBad', 'Incomplete'],
        })

        self.assertNotValid(
            validator.validate(self.item, self.ra),
            expected_message='Invalid rule'
        )

    def test_status_validation_no_ra(self):
        validator = validators.StatusValidator({
            'name': 'standard check',
            'status': ['Standard', 'Incomplete'],
        })

        self.assertNotValid(
            validator.validate(self.item, self.ra),
            expected_message='Invalid State'
        )


class ValidationRunnerTestCase(TestCase):

    def setUp(self):
        self.regex_rule = (
            '- status: any\n'
            '  object: any\n'
            '  checks:\n'
            '    - validator: RegexValidator\n'
            '      field: name\n'
            '      regex: "[abc]+"'
        )
        self.steward_org_1 = MDR.StewardOrganisation.objects.create(
            name='Org 1',
            description="1",
        )
        self.ra = MDR.RegistrationAuthority.objects.create(
            name='RA', definition='RA',
            stewardship_organisation=self.steward_org_1
        )
        self.manager = get_user_model().objects.create_user(email='manager@example.com', password='1234')
        self.ra.managers.add(self.manager)
        self.wg = MDR.Workgroup.objects.create(
            name='WG', definition='WG',
            stewardship_organisation=self.steward_org_1
        )
        self.dbrunner = runners.DatabaseValidationRunner(
            registration_authority=self.ra,
            state=4
        )
        self.client = Client()

    def test_database_runner(self):
        models.RegistryValidationRules.objects.create(rules=self.regex_rule)
        item = MDR.ObjectClass.objects.create(name='OC', definition='oc')
        results = self.dbrunner.validate_metadata([item])
        self.assertEqual(len(results[0]['results']), 1)

    def test_validation_runner_view(self):
        models.RegistryValidationRules.objects.create(rules=self.regex_rule)
        item = MDR.ObjectClass.objects.create(name='OC', definition='oc')
        rr = ReviewRequest.objects.create(
            registration_authority=self.ra,
            requester=self.manager,
            workgroup=self.wg,
            target_registration_state=MDR.STATES.standard
        )
        rr.concepts.add(item)

        self.client.login(email=self.manager.email, password='1234')
        response = self.client.get(reverse('aristotle_reviews:request_checks', args=[rr.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['total_results']), 1)

    def test_validation_runner_rulesets_return_an_empty_list_when_default_value_of_validation_rule_is_an_empty_string(self):
        models.RegistryValidationRules.objects.create(rules='')
        results = self.dbrunner.get_rulesets()
        self.assertEqual(results, [])
