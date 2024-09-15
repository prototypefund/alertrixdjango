from django import forms
from django.utils.translation import gettext as _

from . import alert_channel
from . import company
from . import unit
from .. import models


class WidgetLoginForm(
    forms.ModelForm,
):
    class Meta:
        model = models.Widget
        fields = [
            'id',
            'activation_secret',
        ]
        widgets = {
            'id': forms.HiddenInput(
            ),
        }

    def clean_id(self):
        if not models.Widget.objects.filter(id=self.data.get('id')).exists():
            return _('widget does not exist')
        return self.data.get('id')

    def clean_activation_secret(self):
        if self.instance.activation_secret and self.data.get('activation_secret') != self.instance.activation_secret:
            self.add_error(
                'activation_secret',
                _('invalid activation secret')
            )
        return self.data.get('activation_secret')
