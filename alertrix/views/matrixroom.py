import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from .. import models


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
                if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else None
            ),
            power_level_override=(
                {
                    'users': {
                        self.object.responsible_user.user_id: 100,
                        str(self.request.user.matrix_id): 100,
                    },
                }
                if self.request.user.groups.filter(name=settings.MATRIX_VALIDATED_GROUP_NAME).exists() else None
            ),
            space=True,
            **kwargs,
        )

    def ensure_matrix_room_id(self, form):
        """
        Make sure this object has a valid matrix room associated
        :return:
        """
        if not self.object.matrix_room_id:
            matrix_space_id = async_to_sync(self.create_matrix_room)(
                **self.get_matrix_room_args(
                    form=form,
                ),
            )
            if matrix_space_id:
                if self.request.user.matrix_id:
                    messages.success(
                        self.request,
                        _('%(user_id)s has been invited') % {
                            'user_id': self.request.user.matrix_id,
                        },
                    )
            self.object.matrix_room_id = matrix_space_id

    async def create_matrix_room(
            self,
            **kwargs,
    ):
        client: nio.AsyncClient = await self.object.responsible_user.get_client()
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
        user = await sync_to_async(getattr)(matrix_room, 'responsible_user')
        client: nio.AsyncClient = await user.get_client()
        if client is not None:
            response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
                room_id=room_id,
                event_type=event_type,
                content=content,
                state_key=state_key,
            )

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.responsible_user = form.cleaned_data['responsible_user']
        self.ensure_matrix_room_id(
            form=form,
        )
        for state_event in self.get_matrix_state_events(
                form=form,
        ):
            async_to_sync(self.room_put_state)(
                event_type=state_event.pop('type'),
                **state_event,
            )
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())
