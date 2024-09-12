import argparse
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

from alertrix import models
from alertrix import querysets


async def add_widget_to_chat(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessage,
        args: argparse.Namespace = None,
):
    try:
        await get_user_model().objects.aget(matrix_id=event.sender)
    except get_user_model().DoesNotExist:
        await client.room_send(
            room.room_id,
            'm.room.message',
            {
                'msgtype': 'm.text',
                'body': _('user not registered'),
            },
            ignore_unverified_devices=True,
        )
        return
    # verify that this happens in a direct message
    try:
        dm = await querysets.aget_direct_message_for(
            event.sender,
            client.user_id,
        )
        room_id = dm.room_id
    except mas_models.Room.DoesNotExist:
        await client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'msgtype': 'm.notice',
                'body': _('widgets can only be created in direct messages'),
            },
        )
        return
    if room_id != room.room_id:
        await client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'msgtype': 'm.notice',
                'body': 'https://matrix.to/#/%(room_id)s' % {
                    'room_id': room_id,
                },
                'm.relates_to': {
                    'm.in_reply_to': {
                        'event_id': event.event_id,
                    },
                },
            },
        )
    # Create the widget
    room_id = room_id
    event_type = 'im.vector.modular.widgets'
    widget_id_raw = '%(room)s_%(user)s_%(tms)s_' % {
        'room': slugify(room_id),
        'user': slugify(event.sender),
        'tms': int(timezone.now().timestamp()),
    }
    widget_id_max_length = 128
    widget_id = widget_id_raw[0:min(len(widget_id_raw), 128)]
    if len(widget_id) < widget_id_max_length:
        widget_id += secrets.token_urlsafe(widget_id_max_length - len(widget_id))
    content = {
        'type': 'm.custom',
        'url': '%(scheme)s://%(host)s/?%(args)s' % {
            'scheme': settings.ALERTRIX_WIDGET_SCHEME,
            'host': settings.ALERTRIX_WIDGET_HOST,
            'args': urlencode({
                'widgetId': widget_id,
            }),
        },
        'name': settings.SERVICE_NAME,
        'data': {
        },
    }
    widget = models.Widget(
        id=widget_id,
        room=await mas_models.Room.objects.aget(room_id=room_id),
        user_id=event.sender,
        activation_secret='',
    )
    await widget.asave()
    room_put_state_response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
        room_id=room_id,
        event_type=event_type,
        content=content,
        state_key=widget_id,
    )
    if type(room_put_state_response) is nio.RoomPutStateError:
        await client.room_send(
            room_put_state_response.room_id,
            'm.room.message',
            {
                'msgtype': 'm.notice',
                'body': '%(status)s: %(message)s' % {
                    'status': room_put_state_response.status_code,
                    'message': room_put_state_response.message,
                },
            },
        )
        return
    # Set the room layout
    layout_content = {
        'widgets': {
            widget_id: {
                'container': 'top',
            },
        },
    }
    await client.room_put_state(
        room_id=room_id,
        event_type='io.element.widgets.layout',
        content=layout_content,
        state_key='',
    )
