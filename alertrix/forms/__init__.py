from django import forms
from django.utils.translation import gettext as _

from . import company
from . import unit
from .. import models


class WidgetLoginForm(
    forms.ModelForm,
):
    class Meta:
        model = models.Widget
        fields = [
            'activation_secret',
        ]

    def clean_activation_secret(self):
        if self.instance.activation_secret and self.data.get('activation_secret') != self.instance.activation_secret:
            self.add_error(
                'activation_secret',
                _('invalid activation secret')
            )
        return self.data.get('activation_secret')
