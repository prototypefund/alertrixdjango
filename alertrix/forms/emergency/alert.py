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
