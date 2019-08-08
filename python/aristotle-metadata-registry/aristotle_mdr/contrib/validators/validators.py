from typing import List, Tuple
import re
from aristotle_mdr import models
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.utils.module_loading import import_string

from aristotle_mdr.models import STATES


class BaseValidator:
    allowed_types: List[str] = []

    def __init__(self, rule):
        if 'validator' not in rule.keys():
            rule['validator'] = str(self.__class__.__name__)
        if 'name' in rule:
            self.name = rule['name']
        else:
            self.name = 'Unnamed {}'.format(rule['validator'])
        self.rule = rule

    def get_name(self):
        return self.name

    def validate(self, item, *args, **kwargs):
        try:
            return self._validate(item, *args, **kwargs)
        except:
            return False, "Invalid rule"

    def _validate(self, item, **kwargs) -> Tuple[bool, str]:
        # To be overwritten in child
        # Should return status, message
        raise NotImplementedError


class RegexValidator(BaseValidator):

    def _validate(self, item, ra=None):
        field_data = getattr(item, self.rule['field'])
        regex = self.rule['regex'].lstrip().rstrip()
        match = re.fullmatch(regex, field_data)
        is_valid = match is not None
        message = ""
        if not is_valid:
            message = "Text '{}' does not match required pattern.".format(field_data)
        return is_valid, message


class RelationValidator(BaseValidator):
    errors = {
        'NOT_FK': "Field '{}' is not a foreign key. Cannot test",
        'NOT_FOUND': "Field '{}' does not exist",
        "NOT_LINKED": "Field '{}' has no related object",
    }

    def _validate(self, item, ra=None):
        from django.db.models import ForeignKey
        try:
            field_name = self.rule['field']
            field = item.__class__._meta.get_field(field_name)
            if not issubclass(type(field), ForeignKey):
                return False, self.errors['NOT_FK'].format(field_name)

            field_data = getattr(item, field_name)

            is_valid = field_data is not None
            message = ""
            if not is_valid:
                message = self.errors['NOT_LINKED'].format(field_name)
            return is_valid, message
        except FieldDoesNotExist:
            return False, self.errors['NOT_FOUND'].format(field_name)


class UniqueValuesValidator(BaseValidator):
    """
    Checks to see if a Value Domain has unique permissible values
    and/or supplementary values.
    """
    allowed_types = ['aristotle_mdr.valueDomain']

    def _validate(self, item, ra=None):
        entries = {}
        codes = item.permissiblevalue_set.all().values_list('value', flat=True)
        for code in codes:
            if code in entries.keys():
                entries[code]['pv'] += 1
            else:
                entries[code] = {'pv': 1, 'sv': 0}
        codes = item.supplementaryvalue_set.all().values_list('value', flat=True)
        for code in codes:
            if code in entries.keys():
                entries[code]['sv'] += 1
            else:
                entries[code] = {'sv': 1, 'pv': 0}

        messages = []
        valid = True
        for code, result in entries.items():
            if result['pv'] == 1 and result['sv'] == 0:
                continue
            if result['pv'] == 0 and result['sv'] == 1:
                continue
            if result['pv'] > 1:
                valid = False
                messages.append("Value '{}' is a permissible value more than once - it appeared {} times".format(code, result['pv']))
            if result['sv'] > 1:
                valid = False
                messages.append("Value '{}' is a supplementary value more than once - it appeared {} times".format(code, result['sv']))
            if result['pv'] > 0 and result['sv'] > 0:
                valid = False
                messages.append("Value '{}' is a permissible and supplementary value".format(code))
        return valid, "\n".join(messages)


class StatusValidator(BaseValidator):

    def _validate(self, item, ra=None):
        if not ra:
            return False, 'Invalid rule'

        allowed_statuses = self.rule['status']
        allowed_states = []

        for status in allowed_statuses:
            state = getattr(models.STATES, status.lower(), None)
            if state is None:
                return False, 'Invalid rule'

            allowed_states.append(state)

        statuses = models.Status.objects.filter(
            concept=item._concept_ptr,
            registrationAuthority=ra,
        ).order_by(
            '-effective_date',
            '-created'
        )

        if not statuses.exists():
            return False, 'Invalid State'

        last_status = statuses.first()
        last_state = last_status.state

        if last_state in allowed_states:
            return True, 'Valid State'
        else:
            return False, 'Invalid State'
