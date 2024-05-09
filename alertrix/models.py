from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from matrixappservice.handler import Handler as ApplicationServiceHandler
from matrixappservice.matrix.action import MatrixAction
from matrixappservice.models import User as MatrixUser


class User(
    AbstractUser,
):
    USERNAME_FIELD = 'matrix_id'
    username = None
    matrix_id = models.TextField(
        'Matrix ID',
        primary_key=True,
        help_text='@user:example.com',
    )

    def __str__(self):
        return str(self.__getattribute__(self.USERNAME_FIELD))


class Handler(
    models.Model,
    ApplicationServiceHandler,
):
    application_service = models.OneToOneField(
        ApplicationServiceRegistration,
        on_delete=models.CASCADE,
    )
    users = models.ForeignKey(
        Group,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )

    async def on_m_room_message(
            self,
            request,
            event,
    ):
        app_service = await sync_to_async(self.__getattribute__)('application_service')
        as_client: nio.AsyncClient = await app_service.get_matrix_client()
        joined_members_resp = await as_client.joined_members(
            event['room_id'],
        )
        members = [
            str(member.user_id)
            for member in joined_members_resp.members
        ]
        user: MatrixUser = await MatrixUser.objects.filter(
            user_id__in=members,
        ).afirst()
        device = await user.device_set.afirst()
        client = await user.get_client()
        if event['type'] == 'm.room.message' and event['content']['body'] == 'ping':
            yield MatrixAction(
                client=client,
                args=nio.Api.room_send(
                    access_token=device.access_token,
                    room_id=event['room_id'],
                    event_type='m.room.message',
                    body={
                        'body': 'pong',
                        'msgtype': 'm.text',
                    },
                    tx_id=device.latest_transaction_id,
                ),
            )
            device.latest_transaction_id += 1
            await device.asave()

    async def on_room_invite(
            self,
            request,
            event,
            user: MatrixUser,
    ):
        async for matrix_action in ApplicationServiceHandler.on_room_invite(
            self,
            request,
            event,
            user,
        ):
            yield matrix_action
        client: nio.AsyncClient = await user.get_client()
        device = await user.get_device()


class MatrixRoom(
    models.Model,
):
    matrix_room_id = models.TextField(
    )
    responsible_user = models.ForeignKey(
        MatrixUser,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )

    async def aget_room_info(
            self,
    ):
        mx_user = await sync_to_async(self.__getattribute__)('responsible_user')
        if mx_user is None:
            return []
        client: nio.AsyncClient = await mx_user.get_client()
        room_info = await client.room_get_state(
            str(self.matrix_room_id),
        )
        if type(room_info) is nio.RoomGetStateError:
            logging.error(
                room_info,
            )
            return []
        return room_info.events

    def get_room_info(
            self,
    ):
        return async_to_sync(self.aget_room_info)()
