from typing import Dict
from django import forms
from django.forms.widgets import TextInput, CheckboxSelectMultiple, Select

from django.utils.safestring import mark_safe


class NameSuggestInput(TextInput):
    def __init__(self, *args, **kwargs):
        self.suggest_fields = kwargs.pop('name_suggest_fields')
        self.separator = kwargs.pop('separator', '-')
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        out = super().render(name, value, attrs)
        if self.suggest_fields:
            button = "<button class=\"btn btn-default\" type='button' data-separator='{}' data-suggest-fields='{}'>Suggest</button>".format(self.separator, ",".join(self.suggest_fields))
            out = "<div class='suggest_name_wrapper'>{}{}</div>".format(out, button)
        return mark_safe(out)


# Thanks http://stackoverflow.com/questions/6727372/
class RegistrationAuthoritySelect(forms.Select):
    def render(self, name, value, renderer=None, **kwargs):
        attrs = kwargs.get('attrs', None)
        if value is not None:
            attrs['disabled']='disabled'
            _id = attrs.get('id')
            # Insert a hidden field with the same name as 'disabled' fields aren't submitted.
            # http://stackoverflow.com/questions/368813/
            hidden_input_with_value = '<input type="hidden" id="%s" name="%s" value="%s" />' % (_id, name, value)
            attrs['id'] = _id + "_disabled"
            name = name + "_disabled"
            rendered = super().render(name, value, **kwargs)
            return mark_safe(rendered + hidden_input_with_value)
        else:
            return super().render(name, value, renderer=None, **kwargs)


class TableCheckboxSelect(CheckboxSelectMultiple):

    def __init__(self, extra_info, static_info, headers, top_header, order, attrs=None, choices=(), deselections=False, **kwargs):
        super().__init__(attrs, choices, **kwargs)
        self.extra_info = extra_info
        self.static_info = static_info
        self.order = order
        self.header_list = []
        self.deselections = deselections

        for field in order:
            header = headers[field]
            if header:
                self.header_list.append(header)

        self.top_header = top_header
        self.badperms = False

    template_name = 'aristotle_mdr/widgets/table_checkbox_select.html'
    option_template_name = 'aristotle_mdr/widgets/table_checkbox_option.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option_extra = self.extra_info[option['value']]
        option_extra_list = []

        for field in self.order:

            if field in ['input', 'label']:
                continue

            try:
                value = option_extra[field]
            except KeyError:
                value = None

            if not value:
                try:
                    value = self.static_info[field]
                except KeyError:
                    value = None

            option_extra_list.append(value)

        option['extra'] = option_extra_list
        option['permission'] = option_extra['perm']
        option['checked'] = option_extra['checked']

        if not option['permission']:
            self.badperms = True

        return option

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        context.update({
            'static_info': self.static_info,
            'headers': self.header_list,
            'badperms': self.badperms,
            'top_header': self.top_header,
            'deselections': self.deselections
        })

        return context


class MultiTextWidget(TextInput):
    template_name = 'aristotle_mdr/widgets/multi_input.html'
    subwidget = TextInput

    class Media:
        js = ('aristotle_mdr/multifield.js',)

    def __init__(self, *args, **kwargs):
        if 'subwidget' in kwargs:
            self.subwidget = kwargs.pop('subwidget')

        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        # Modified from MultiHiddenWidget
        context = super().get_context(name, value, attrs)
        final_attrs = context['widget']['attrs']
        id_ = context['widget']['attrs'].get('id')

        subwidgets = []
        for index, value_ in enumerate(context['widget']['value']):
            widget_attrs = final_attrs.copy()
            name_ = '{}-{}'.format(name, index)
            if id_:
                # An ID attribute was given. Add a numeric index as a suffix
                # so that the inputs don't all have the same ID attribute.
                widget_attrs['id'] = '%s-%s' % (id_, index)
            widget = self.subwidget()
            widget.is_required = self.is_required
            subwidgets.append(widget.get_context(name_, value_, widget_attrs)['widget'])

        context['widget']['subwidgets'] = subwidgets
        return context

    def format_value(self, value):
        if not value:
            return ['']
        else:
            return value

    def value_from_datadict(self, data, files, name):
        prefix = name + '-'
        values = []
        for key in data.keys():
            if key.startswith(prefix):
                values.append(data[key])

        return values


class DataAttrSelect(Select):
    """Select widget that adds extra data attributes to <option> elements"""
    def __init__(self, attrs=None, choices=(), data: Dict[str, Dict[str, str]] = {}):
        super().__init__(attrs, choices)
        self.data = data

    def create_option(self, *args, **kwargs):
        option: Dict = super().create_option(*args, **kwargs)
        for data_attr, values in self.data.items():
            if option['value'] in values:
                option['attrs'][data_attr] = values[option['value']]

        return option
