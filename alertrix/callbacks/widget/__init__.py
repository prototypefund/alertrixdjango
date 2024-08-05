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
