import json
import re

from django import forms
from django.forms import fields as _fields
from django.forms import widgets as _widgets
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _


class CoordinateWidget(
    forms.MultiWidget,
):
    def __init__(self, widgets=None, attrs=None):
        super().__init__(
            widgets or tuple(
                _widgets.NumberInput(
                    attrs={
                        'step': '0.00001',
                    },
                )
                for _ in range(2)
            ),
            attrs,
            )

    def decompress(self, value):
        return json.loads(value or '[null, null]')

    def value_from_datadict(self, data, files, name):
        d = []
        for key in data.keys():
            if key == name:
                # the data is likely to come from the cli
                return data.get(key)
            if not key.startswith(name):
                continue
            if not re.match(r'_\d+', key[len(name):]):
                continue
            d.append(float(data.get(key)))
        return d


class CoordinateField(
    _fields.MultiValueField,
):
    widget = CoordinateWidget

    def __init__(self, fields=None, *args, **kwargs):
        super().__init__(
            fields or tuple(
                _fields.FloatField(
                    min_value=-180,
                    max_value=180,
                )
                for _ in range(2)
            ),
            *args, **kwargs
        )

    def compress(self, data_list):
        return data_list


class AlertForm(
    forms.Form,
):
    code = forms.CharField(
    )
    description = forms.CharField(
        widget=forms.Textarea(
        ),
        required=False,
    )
    units = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
    )
    location = CoordinateField(
        required=False,
    )
    address = forms.CharField(
        label=gettext('address'),
        required=False,
        widget=forms.Textarea(
        ),
    )

    class Meta:
        require_one_of = [
            ('location', 'address'),
        ]

    def clean(self):
        for group in self.Meta.require_one_of:
            if not any([self.cleaned_data.get(key) for key in group]):
                self.add_error(
                    '__all__',
                    _('you need to specify any of the following fields: %(field_labels)s') % {
                        'field_labels': ', '.join([
                            self.fields[key].label or key
                            for key in group
                        ])
                    },
                    )
        return super().clean()

    def clean_location(self):
        return (
            float(self.data.get('location_0')),
            float(self.data.get('location_1')),
        )
