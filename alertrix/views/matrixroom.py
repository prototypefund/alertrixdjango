import nio
import synapse.appservice
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from matrixappservice import models as mas_models


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

    def get_matrix_room_args(self, form):
        """
        Return the arguments used to create the room.
        :param form:
        :return:
        """
        return dict(
            name=form.data['name'],
            topic=form.data['description'],
            federate=form.data['federate'],
            initial_state=[
            ],
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
