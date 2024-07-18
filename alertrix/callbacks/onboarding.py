import secrets

import nio
from django.conf import settings
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.text import slugify
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient
from matrixappservice import models as mas_models

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
                message_type='m.room.message',
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
            await client.room_forget(
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


async def ensure_encryption(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessage,
):
    if not settings.ALERTRIX_ENFORCE_ENCRYPTION:
        # This alertrix instance does not enforce encryption
        return
    if client.rooms[room.room_id].encrypted:
        # This room already is encrypted
        return
    if event.source['content'].get('net.alertrix.request_encryption') is not None:
        # This request likely comes from us or another alertrix bot
        return
    enable_encryption_event = nio.EnableEncryptionBuilder().as_dict()
    room_put_state_response = await client.room_put_state(
        room_id=room.room_id,
        event_type=enable_encryption_event.pop('type'),
        **enable_encryption_event,
    )
    if type(room_put_state_response) is nio.RoomPutStateError:
        await client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'net.alertrix.request_encryption': '',
                'msgtype': 'm.notice',
                'body': _('please enable encryption'),
            }
        )


async def add_widget_to_chat(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessage,
):
    if event.source['content']['body'].startswith('start'):
        # verify that this happens in the primary direct message
        try:
            dm = await models.DirectMessage.objects.aget(
                responsible_user__user_id=client.user_id,
                with_user=event.sender,
            )
        except models.DirectMessage.DoesNotExist:
            # We likely joined the room, but it did not get registered as direct message in the first place
            return
        if dm.matrix_room_id == room.room_id:
            # Create the widget
            room_id = room.room_id
            event_type = 'im.vector.modular.widgets'
            widget_id = '%(room)s_%(user)s_%(tms)s_%(random)s' % {
                'room': slugify(room_id),
                'user': slugify(event.sender),
                'tms': int(timezone.now().timestamp()),
                'random': secrets.token_urlsafe(128),
            }
            content = {
                'type': 'm.custom',
                'url': '%(scheme)s://%(host)s/?%(args)s' % {
                    'scheme': settings.ALERTRIX_WIDGET_SCHEME,
                    'host': settings.ALERTRIX_WIDGET_HOST,
                    'args': urlencode({
                        'widgetId': widget_id,
                    }),
                },
                'name': settings.ALERTRIX_WIDGET_HOST,
                'data': {
                },
            }
            widget = models.Widget(
                id=widget_id,
                room=await models.MatrixRoom.objects.aget(matrix_room_id=room.room_id),
                user_id=event.sender,
            )
            await widget.asave()
            await client.room_put_state(
                room_id=room_id,
                event_type=event_type,
                content=content,
                state_key=widget_id,
            )
            # Set the room layout
            content = {
                'widgets': {
                    widget_id: {
                        'container': 'top',
                    },
                },
            }
            await client.room_put_state(
                room_id=room_id,
                event_type='io.element.widgets.layout',
                content=content,
                state_key='',
            )
        else:
            await client.room_send(
                room_id=room.room_id,
                message_type='m.room.message',
                content={
                    'msgtype': 'm.notice',
                    'body': 'https://matrix.to/#/%(room_id)s' % {
                        'room_id': dm.matrix_room_id,
                    },
                    'm.relates_to': {
                        'm.in_reply_to': {
                            'event_id': event.event_id,
                        },
                    },
                },
            )
