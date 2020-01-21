from aristotle_mdr.tests.utils import AristotleTestUtils
from aristotle_mdr.utils.utils import get_concept_models
from aristotle_mdr.contrib.serializers.utils import get_concept_fields

from django.conf import settings
from django.test import TestCase, override_settings
from django.db.models import DateTimeField, DateField

from ddf import G  # Django Dynamic Fixture
from typing import List, Optional
from datetime import datetime


def generate_failure_report(failures: List) -> None:
    failure_str = '\n'
    if failures:
        for failure in failures:
            failure_str += f'{str(failure)} \n'
        raise AssertionError(failure_str)


def normalize_string(string: str) -> str:
    return ''.join(string.casefold().split())


def normalize_date(datetime: Optional[datetime]) -> str:
    return datetime.strftime('%B %Y')


def generate_item_test(model):
    """ Helper function to generate a test that goes to an item page and checks that all the fields are there"""

    @override_settings()
    def test(self):
        """The actual testing function"""
        aristotle_settings = settings.ARISTOTLE_SETTINGS
        aristotle_settings['CONTENT_EXTENSIONS'].extend(['comet', 'aristotle_dse', 'aristotle_glossary'])

        with self.settings(ARISTOTLE_SETTINGS=aristotle_settings):
            item = G(model)

        # Login a superuser
        self.login_superuser()

        # Go to the item page
        response = self.client.get(item.get_absolute_url())
        self.assertEqual(response.status_code, self.OK)

        # Check that all the concept (the fields that are directly on the concept) fields appear with their content
        failures = []
        for field in get_concept_fields(model):
            value = field.value_from_object(item)

            # Unify cases and whitespace
            field_name = normalize_string(field.name.replace("_", " "))
            content = normalize_string(str(response.content))

            # Replace modified with last updated to correspond with display on item page
            if field.name == 'modified':
                field_name = normalize_string('Last updated')

            # Normalize display of date objects

            if value is not None:
                if issubclass(type(field), (DateTimeField, DateField)):
                    value = normalize_string(normalize_date(value))
                if str(value) not in content and field_name not in self.excluded_fields:
                    failures.append(f"Can't find field value: {value} in response")

            if field_name not in content and field_name not in self.excluded_fields:
                failures.append(f"Can't find field_name: '{field.name}' in response")

        generate_failure_report(failures)

    test.__doc__ = f'Test that all fields are visible on the item page for {model.__name__}'
    return test


class FieldsMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        # Iterate over all concept models, creating one test per model
        metaclass = super().__new__(mcs, name, bases, attrs)

        for model in get_concept_models():
            test = generate_item_test(model)
            setattr(metaclass, f'test_all_fields_appear_on_{model.__name__.lower()}', test)

        return metaclass


@override_settings(DDF_FILL_NULLABLE_FIELDS=True)
class FieldsTestCase(AristotleTestUtils, TestCase, metaclass=FieldsMetaclass):
    """A class to formally check that fields appear on the item page"""
    excluded_fields = [
        'id',
        'byte_size',
        'submitter',
        'symbol'
    ]

    def setUp(self) -> None:
        super().setUp()
