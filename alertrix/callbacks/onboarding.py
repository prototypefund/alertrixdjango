import secrets

import nio
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient

from .. import models


async def on_room_invite(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.InviteMemberEvent,
):
    if event.state_key != client.user_id:
        return
    if event.membership == 'invite':
        await client.join(
            room.room_id,
        )
    if event.content.get('is_direct', False):
        try:
            # Check if there already is a direct message room for this combination of users…
            dm = await models.DirectMessage.objects.aget(
                responsible_user__user_id=client.user_id,
                with_user=event.sender,
            )
            # … direct the user to that room …
            await client.room_send(
                room_id=room.room_id,
                event_type='m.room.message',
                body={
                    'msgtype': 'm.text',
                    'body': 'https://matrix.to/#/%(room_id)s' % {
                        'room_id': dm.matrix_room_id,
                    },
                }
            )
            # … and leave this room.
            await client.room_leave(
                room.room_id,
            )
        except models.DirectMessage.DoesNotExist:
            await models.DirectMessage.objects.acreate(
                responsible_user=await mas_models.User.objects.aget(
                    user_id=client.user_id,
                ),
                matrix_room_id=room.room_id,
                with_user=await models.User.objects.aget(
                    matrix_id=event.sender,
                ),
            )
