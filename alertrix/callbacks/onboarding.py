import secrets

import nio
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.text import slugify
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient
from matrixappservice import models as mas_models

from .. import models
from .. import querysets


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
            our_direct_messages = mas_models.Event.objects.filter(
                state_key=client.user_id,
                unsigned__prev_content__is_direct=True,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            their_direct_messages = mas_models.Event.objects.filter(
                state_key=event.sender,
                unsigned__prev_content__is_direct=True,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            dm = await mas_models.Room.objects.aget(
                room_id__in=await our_direct_messages.intersection(their_direct_messages).aget(),
                room_is__ne=room.room_id,
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
        except mas_models.Event.DoesNotExist:
            pass


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
            mu = await models.MainUserKey.objects.aget(
                service=await mas_models.User.objects.filter(
                    user_id=client.user_id,
                ).values_list('app_service', flat=True).aget(),
            )
            our_direct_messages = mas_models.Event.objects.filter(
                state_key=mu.user_id,
                unsigned__prev_content__is_direct=True,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            their_direct_messages = mas_models.Event.objects.filter(
                state_key=event.sender,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            dm = await mas_models.Room.objects.aget(
                room_id__in=our_direct_messages.intersection(their_direct_messages),
            )
        except models.MainUserKey.DoesNotExist:
            app_service = await mas_models.User.objects.aget(
                user_id=client.user_id,
            )
            mu = await models.MainUserKey.objects.aget(
                service=app_service,
            )
            await client.room_send(
                room_id=room.room_id,
                message_type='m.room.message',
                content={
                    'msgtype': 'm.notice',
                    'body': 'https://matrix.to/#/%(user_id)s' % {
                        'user_id': mu.user_id,
                    },
                    'm.relates_to': {
                        'm.in_reply_to': {
                            'event_id': event.event_id,
                        },
                    },
                }
            )
            return
        if dm.room_id == room.room_id:
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
                room=await mas_models.Room.objects.aget(room_id=room.room_id),
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
                        'room_id': dm.room_id,
                    },
                    'm.relates_to': {
                        'm.in_reply_to': {
                            'event_id': event.event_id,
                        },
                    },
                },
            )
