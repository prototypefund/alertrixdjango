from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from . import models


class CreateRegistration(
    forms.ModelForm,
):
    class Meta:
        title = _('create registration token')
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
        cleaned_matrix_id = self.data.get('valid_for_matrix_id').strip()
        if not cleaned_matrix_id.startswith('@'):
            self.add_error(
                'valid_for_matrix_id',
                _('a matrix user id always starts with "@"'),
            )
            return
        if len(cleaned_matrix_id.split(':')) != 2:
            self.add_error(
                'valid_for_matrix_id',
                _('there should be exactly one ":" in your full username'),
            )
            return
        if len(cleaned_matrix_id.lstrip('@').split(':')[0]) <= 0:
            self.add_error(
                'valid_for_matrix_id',
                _('you need to enter you full matrix user id including the localpart'),
            )
            return
        if len(cleaned_matrix_id.split(':')[1]) <= 0:
            self.add_error(
                'valid_for_matrix_id',
                _('you need to enter you full matrix user id including the server name'),
            )
            return
        try:
            user = get_user_model().objects.get(
                matrix_id=cleaned_matrix_id,
            )
            if user.has_usable_password():
                raise AttributeError()
        except (
            get_user_model().DoesNotExist,
            AttributeError
        ):
            self.add_error(
                'valid_for_matrix_id',
                _('If this user exists, they are not prepared to set a password'),
            )
        finally:
            return cleaned_matrix_id


class CreateFirstUserForm(
    UserCreationForm,
):

    class Meta:
        title = _('create admin account')
        model = get_user_model()
        fields = [
            'matrix_id',
        ]
        widgets = {
            'matrix_id': forms.Textarea(
                attrs={
                    'rows': 1,
                },
            ),
        }


class CreateUserForm(
    UserCreationForm,
):
    token = forms.CharField(
    )

    class Meta:
        title = _('create user')
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
