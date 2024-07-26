import abc
import logging

import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django import views
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _



class CreateMatrixRoom(
):
    """
    Parent CreateView to create MatrixRoom objects.
    """

    def get_form_kwargs(self):
        kwargs = {
            'user': self.request.user,
            **super().get_form_kwargs(),
        }
        return kwargs

    def get_matrix_state_events(self, form):
        return []

    def get_matrix_room_args(
            self,
            form,
            **kwargs,
    ):
        """
        Return the arguments used to create the room.
        :param form:
        :return:
        """
        return dict(
            name=form.data['name'],
            topic=form.data['description'],
            federate=form.data['federate'] == 'on' if 'federate' in form.data else False,
            initial_state=self.get_matrix_state_events(
                form=form,
            ),
            invite=(
                [
                    str(self.request.user.matrix_id)
                ]
                if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else list()
            ),
            power_level_override=(
                {
                    'users': {
                        self.responsible_user.user_id: 100,
                        str(self.request.user.matrix_id): 100,
                    },
                }
                if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else None
            ),
            space=True,
            **kwargs,
        )

    async def create_matrix_room(
            self,
            **kwargs,
    ):
        client: nio.AsyncClient = await self.responsible_user.aget_client()
        response: nio.RoomCreateResponse = await client.room_create(
            **kwargs
        )
        if type(response) is nio.RoomCreateError:
            messages.warning(
                self.request,
                _('failed to create matrix space: %(errcode)s %(error)s') % {
                    'errcode': response.status_code,
                    'error': response.message,
                },
            )
            return None
        return response.room_id

    async def room_put_state(
            self,
            room_id: str,
            event_type: str,
            content,
            state_key: str = "",
    ):
        matrix_room = await models.MatrixRoom.objects.aget(matrix_room_id=room_id)
        client: nio.AsyncClient = await self.responsible_user.aget_client()
        if client is not None:
            response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
                room_id=room_id,
                event_type=event_type,
                content=content,
                state_key=state_key,
            )

    def form_valid(self, form):
        self.form = form
        if not form.cleaned_data.get('room_id'):
            async_to_sync(self.create_matrix_room)(
                **self.get_matrix_room_args(
                    form=form,
                ),
            )
        return HttpResponseRedirect(self.get_success_url())
