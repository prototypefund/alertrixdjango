from django import forms
from django.utils.translation import gettext_lazy as _
from matrixappservice import models as matrixappservice

from . import matrixroom
from .. import models
from ..events import v1 as events


class AlertChannelCreateForm(
    matrixroom.MatrixRoomCreateForm,
):

    class Meta(
        matrixroom.MatrixRoomCreateForm.Meta,
    ):
        advanced = matrixroom.MatrixRoomCreateForm.Meta.advanced + [
            'overwrite',
            'description',
        ]
        optional = matrixroom.MatrixRoomCreateForm.Meta.optional + [
            'overwrite',
        ]

    pattern = forms.CharField(
        widget=forms.TextInput(
        ),
        required=False,
        initial='',
    )
    overwrite = forms.BooleanField(
        initial=False,
        required=False
    )
    company = forms.ChoiceField(
        label=_('company'),
        choices=models.AlertChannel.objects.none(),
    )

    def clean_company(self):
        return self.data.get('company')

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop('choices', {})
        super().__init__(*args, **kwargs)
        for key in choices:
            self.fields[key].choices = choices[key]

    def clean_overwrite(self):
        return self.data.get('overwrite') == 'on'

    def clean_pattern(self):
        pattern = self.data.get('pattern')
        if all([
                matrixappservice.Event.objects.filter(
                    room=models.DirectMessage.objects.get_for(
                        self.user.matrix_id,
                        matrixappservice.Event.objects.get(
                            room__room_id=self.clean_company(),
                            type=events.AlertrixCompany.get_type(),
                        ).content['inbox'],
                        valid_memberships=[
                            'join',
                            'invite',
                        ],
                    ),
                    type=events.AlertrixEmergencyAlertChannel.get_type(),
                    content__inbox__isnull=False,
                    state_key=pattern,
                ).exists(),
                not self.clean_overwrite(),
        ]):
            self.add_error(
                'pattern',
                _('there already is an alert channel for this pattern pattern and an overwrite is not requested'),
            )
        return pattern
