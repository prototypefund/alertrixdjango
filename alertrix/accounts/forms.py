from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from . import models


class CreateRegistration(
    forms.ModelForm,
):
    class Meta:
        model = models.RegistrationToken
        fields = [
            'valid_for_matrix_id',
        ]
        widgets = {
            'valid_for_matrix_id': forms.Textarea(
                attrs={
                    'rows': 1,
                    'style': ';'.join([
                        'resize: none',
                    ]),
                },
            ),
        }
        labels = {
            'valid_for_matrix_id': _('matrix id'),
        }
        help_texts = {
            'valid_for_matrix_id': get_user_model()._meta.get_field('matrix_id').help_text,
        }

    submit_text = _('register')

    def clean_valid_for_matrix_id(self):
        return self.data.get('valid_for_matrix_id').strip()


class CreateUserForm(
    UserCreationForm,
):
    token = forms.CharField(
    )

    class Meta:
        model = get_user_model()
        fields = [
            'token',
            'matrix_id',
        ]
        widgets = {
            'matrix_id': forms.Textarea(
                attrs={
                    'rows': 1,
                    'style': ';'.join([
                        'resize: none',
                    ]),
                },
            ),
        }

    def clean_token(self):
        try:
            token: models.RegistrationToken = models.RegistrationToken.objects.get(
                token=self.data['token'],
                valid_for_matrix_id=self.data['matrix_id'],
            )
        except models.RegistrationToken.DoesNotExist:
            self.add_error(
                'token',
                _('not a valid token for %(user_id)s') % {
                    'user_id': self.data['matrix_id'],
                },
            )
            return
        if not token.is_valid():
            if not self.has_error('token'):
                self.add_error(
                    'token',
                    _('not a valid token'),
                )
