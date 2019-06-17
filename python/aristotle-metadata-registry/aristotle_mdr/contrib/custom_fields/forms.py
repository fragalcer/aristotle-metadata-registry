from typing import Iterable, List, Dict, Set
from django import forms
from django.contrib.contenttypes.models import ContentType

from aristotle_mdr.contrib.custom_fields.types import type_field_mapping
from aristotle_mdr.contrib.custom_fields.models import CustomField, CustomValue
from aristotle_mdr.models import _concept
from aristotle_mdr.utils.utils import get_concept_content_types
from aristotle_mdr.contrib.custom_fields.constants import CUSTOM_FIELD_STATES

import csv
import itertools


class CustomFieldForm(forms.ModelForm):
    class Meta:
        model = CustomField
        exclude = ['order']

        help_texts = {
            'choices': "Enter a comma separated list of options."
        }

    def get_concept_qs(self):
        mapping = get_concept_content_types()
        ids = [ct.id for ct in mapping.values()]
        return ContentType.objects.filter(id__in=ids).order_by('model')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'allowed_model' in self.fields:
            self.fields['allowed_model'].queryset = self.get_concept_qs()
            self.fields['allowed_model'].empty_label = 'All'


class CustomFieldDeleteForm(forms.Form):

    method = forms.ChoiceField(
        choices=[
            ('migrate', 'Move values to standard slots'),
            ('delete', 'Remove all values')
        ],
        widget=forms.RadioSelect,
        initial='migrate',
    )


class CustomValueFormMixin:
    """Used with concept form"""

    custom_field_names: List[str]
    fields: dict
    cfields: dict
    cleaned_data: dict

    def __init__(self, custom_fields: Iterable[CustomField] = [], **kwargs):
        # This is immediately overridden by __init__ but python type checking demands it
        self.bad_value_custom_fields: Set = set()
        self.initial: Dict

        super().__init__(**kwargs)  # type: ignore

        # Map custom field form names to CustomField objects
        self.cfields = {cf.form_field_name: cf for cf in custom_fields}

        fields_to_remove = []

        # Iterate over mapping
        for custom_fname, custom_field in self.cfields.items():

            key = custom_field.form_field_name

            field = type_field_mapping[custom_field.type]

            field_class = field['field']
            field_default_args = field.get('args', {})

            if issubclass(field_class, forms.ChoiceField):
                # Special case for choice fields
                # Get csv string from CustomField
                values = custom_field.choices
                # Parse lines with csv reader
                csvReader = csv.reader(values.split('\n'))
                # Get a list of lists from csv reader
                choice_lists = [v for v in csvReader]
                # Flatten into list of values
                choice_values = itertools.chain(*choice_lists)
                # Make into 2 tuple
                choices = [('', '------')]
                for val in choice_values:
                    choices.append((val, val))

                if custom_fname in self.initial:
                    value = self.initial[custom_fname]
                    if value not in choice_values:
                        # If there is an initial value that isnt in the option list
                        # Add it as the last option
                        choices.append((value, value + ' (Old Value)'))
                        self.bad_value_custom_fields.add(custom_fname)

                field_default_args['choices'] = choices

            if custom_field.state == CUSTOM_FIELD_STATES.inactive:
                if self.user.is_superuser:  # type: ignore
                    pass
                else:
                    # The Custom Field is set to inactive but visible
                    if key not in self.initial:
                        # If there is no custom value associated, we don't want to display the CustomField
                        fields_to_remove.append(key)
                    else:
                        # There is a custom value associated but it's empty
                        if self.initial[key] == '':
                            if self.user.is_superuser:  # type: ignore
                                pass
                            else:
                                fields_to_remove.append(key)

            if key not in fields_to_remove:
                self.fields[custom_fname] = field_class(
                    required=False,
                    label=custom_field.name,
                    help_text=custom_field.help_text,
                    **field_default_args
                )
        for key in fields_to_remove:
            del self.cfields[key]

    @property
    def custom_fields(self) -> List:
        return [self[fname] for fname in self.cfields.keys()]  # type: ignore

    def save_custom_fields(self, concept: _concept) -> _concept:
        for fname in self.cfields.keys():
            data = self.cleaned_data[fname]
            if data == 'None' or data is None:
                data = ''
            if fname in self.cfields:
                field = self.cfields[fname]
                obj, created = CustomValue.objects.update_or_create(
                    field=field,
                    concept=concept,
                    defaults={'content': str(data)}
                )

        return concept
