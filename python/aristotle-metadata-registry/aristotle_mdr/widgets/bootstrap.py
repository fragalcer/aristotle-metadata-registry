from django.forms.widgets import (
    CheckboxSelectMultiple,
    RadioSelect, DateTimeInput
)

import json

from django.forms.utils import flatatt
from django.utils.html import conditional_escape
from django.utils.encoding import force_text


class BootstrapDropdownSelect(RadioSelect):
    allow_multiple_selected = False
    template_name = "search/forms/widgets/radio.html"
    option_template_name = 'search/forms/widgets/radio_option.html'


class BootstrapDropdownIntelligentDate(BootstrapDropdownSelect):
    template_name = "search/forms/widgets/radio_and_date.html"
    option_template_name = 'search/forms/widgets/radio_option.html'


class BootstrapDropdownSelectMultiple(CheckboxSelectMultiple):
    allow_multiple_selected = True
    template_name = "search/forms/widgets/radio.html"
    option_template_name = 'search/forms/widgets/checkbox_option.html'


class BootstrapDropdownSearchCategoriesSelect(RadioSelect):
    allow_multiple_selected = True
    template_name = "search/forms/widgets/search_radio.html"
    option_template_name = 'search/forms/widgets/checkbox_option.html'


# Lovingly upgraded from the link below to support Django 2+
# https://github.com/tutorcruncher/django-bootstrap3-datetimepicker

class BootstrapDateTimePicker(DateTimeInput):
    template_name = "search/forms/widgets/datetime.html"

    # http://momentjs.com/docs/#/parsing/string-format/
    # http://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
    format_map = (
        ('DDD', r'%j'),
        ('DD', r'%d'),
        ('MMMM', r'%B'),
        ('MMM', r'%b'),
        ('MM', r'%m'),
        ('YYYY', r'%Y'),
        ('YY', r'%y'),
        ('HH', r'%H'),
        ('hh', r'%I'),
        ('mm', r'%M'),
        ('ss', r'%S'),
        ('a', r'%p'),
        ('ZZ', r'%z'),
    )

    def __init__(self, attrs=None, format=None, options=None, div_attrs=None, icon_attrs=None):
        if not icon_attrs:
            icon_attrs = {'class': 'glyphicon glyphicon-calendar'}
        if not div_attrs:
            div_attrs = {'class': 'input-group date'}
        if format is None and options and options.get('format'):
            format = self.conv_datetime_format_js2py(options.get('format'))
        super().__init__(attrs, format)
        if 'class' not in self.attrs:
            self.attrs['class'] = 'form-control'

        div_attrs['class'] += ' dj-datepicker'
        self.div_attrs = div_attrs and div_attrs.copy() or {}
        self.icon_attrs = icon_attrs and icon_attrs.copy() or {}
        self.picker_id = self.div_attrs.get('id') or None
        if options is False:  # datetimepicker will not be initalized when options is False
            self.options = False
        else:
            self.options = options and options.copy() or {}
            if format and not self.options.get('format') and not self.attrs.get('date-format'):
                self.options['format'] = self.conv_datetime_format_py2js(format)

        if self.options:
            self.div_attrs['options'] = json.dumps(self.options)

    @classmethod
    def conv_datetime_format_py2js(cls, format):
        for js, py in cls.format_map:
            format = format.replace(py, js)
        return format

    @classmethod
    def conv_datetime_format_js2py(cls, format):
        for js, py in cls.format_map:
            format = format.replace(js, py)
        return format

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        extra_attrs = dict(type=self.input_type, name=name)
        if self.attrs:
            extra_attrs.update(self.attrs)
        input_attrs = self.build_attrs(attrs, extra_attrs=extra_attrs)

        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            input_attrs['value'] = force_text(self.format_value(value))

        if not self.picker_id:
            self.picker_id = (input_attrs.get('id', '') + '_pickers').replace(' ', '_')
        self.div_attrs['id'] = self.picker_id

        context['div_attrs'] = flatatt({key: conditional_escape(val) for key, val in self.div_attrs.items()})
        context['icon_attrs'] = flatatt({key: conditional_escape(val) for key, val in self.icon_attrs.items()})
        context['input_attrs'] = flatatt({key: conditional_escape(val) for key, val in input_attrs.items()})
        context['picker_id'] = conditional_escape(self.picker_id)
        context['options'] = json.dumps(self.options) or {}

        return context
