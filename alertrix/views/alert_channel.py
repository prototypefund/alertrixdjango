from typing import Optional

import nio
from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from matrixappservice import models as matrixappservice
from matrixappservice.exceptions import MatrixError

from . import matrixroom
from .. import forms
from .. import models
from ..events import v1 as events


class CreateAlertChannel(
    PermissionRequiredMixin,
    matrixroom.CreateMatrixRoom,
):
    permission_required = 'alertrix.add_alertchannel'
    form_class = forms.alert_channel.AlertChannelCreateForm

    def get_success_url(self):
        return reverse(
            'comp.detail',
            kwargs=dict(
                pk=self.form.cleaned_data.get('company'),
            ),
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if 'choices' not in kwargs.keys():
            kwargs['choices'] = {}
        kwargs['choices']['company'] = [
            (company.room_id, company.get_name().content['name'])
            for company in models.Company.objects.filter(
                room_id__in=matrixappservice.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=self.request.user.matrix_id,
                ).values_list(
                    'room__room_id',
                    flat=True,
                ),
            )
        ]
        return kwargs

    def get_users_permission_level(self) -> Optional[dict[str, int]]:
        return {
            self.responsible_user.user_id: 100,
            self.request.user.matrix_id: 50,
        }

    def get_events_default_permission_level(self) -> Optional[int]:
        return 100

    def get_events_permission_level(self) -> Optional[dict[str, int]]:
        return {
            'im.vector.modular.widgets': 50,
            'm.reaction': 0,
            'm.room.avatar': 50,
            'm.room.name': 50,
            'm.room.redaction': 50,
            'm.room.topic': 50,
            'm.space.parent': 50,
        }

    def get_matrix_room_args(
            self,
            form,
            **kwargs,
    ):
        args = super().get_matrix_room_args(form, **kwargs)
        del args['space']
        return args

    def get_matrix_state_events(self, form):
        return super().get_matrix_state_events(form) + [
            nio.EnableEncryptionBuilder().as_dict(),
        ]

    async def aafter_room_creation(
            self,
            room_id: str,
    ):
        dm = await models.DirectMessage.objects.aget_for(
            self.responsible_user.user_id,
            self.request.user.matrix_id,
            valid_memberships=[
                'invite',
                'join',
            ],
        )
        client = await self.responsible_user.aget_client()
        alert_channel_event = events.AlertrixEmergencyAlertChannel(
            inbox=room_id,
            pattern=self.form.cleaned_data.get('pattern'),
        ).get_matrix_data()
        room_put_state_response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
            event_type=alert_channel_event.pop('type'),
            **{
                **alert_channel_event,
                **{
                    'room_id': dm.room_id,
                },
            },
        )
        if type(room_put_state_response) is nio.RoomPutStateResponse:
            messages.success(
                self.request,
                _('a new alert channel has been created'),
            )
        elif type(room_put_state_response) is nio.RoomPutStateError:
            raise MatrixError(
                errcode=room_put_state_response.status_code,
                error=room_put_state_response.message,
            )
        company_id = self.form.cleaned_data.get('company')
        room_put_state_response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
            room_id=company_id,
            event_type='m.space.child',
            state_key=room_id,
            content={
                'via': await sync_to_async(list)(
                    matrixappservice.User.objects.filter(
                        user_id__in=models.Event.objects.filter(
                            type='m.room.member',
                            content__membership='join',
                            room__room_id__in=company_id,
                        ),
                    ).values_list(
                        'homeserver__server_name',
                        flat=True,
                    ),
                ),
            },
        )
        if type(room_put_state_response) is nio.RoomPutStateResponse:
            messages.debug(
                self.request,
                _('alert channel has been added to company'),
            )
        elif type(room_put_state_response) is nio.RoomPutStateError:
            raise MatrixError(
                errcode=room_put_state_response.status_code,
                error=room_put_state_response.message,
            )
        await client.close()

    def form_valid(self, form):
        self.responsible_user = matrixappservice.User.objects.get(
            user_id=matrixappservice.Event.objects.get(
                type=events.AlertrixCompany.get_type(),
                room__room_id=form.cleaned_data.get('company'),
            ).content['inbox'],
        )
        return super().form_valid(form)
