import logging
import traceback

import nio
from asgiref.sync import sync_to_async
from matrixappservice import MatrixClient
from matrixappservice.models import Event

from alertrix.events import v1


async def alert_callback(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        attribute: str,
):
    if event.sender == client.user_id:
        return
    alert_info = event.source['content'][attribute]
    alert = v1.Alert(**alert_info)
    for unit in alert.units:
        member_ids = Event.objects.filter(
            type='m.room.member',
            content__membership='join',
            room__room_id=unit,
        ).values_list('state_key', flat=True)
        our_direct_messages = Event.objects.filter(
            state_key=client.user_id,
            unsigned__prev_content__is_direct=True,
            content__membership='join',
        ).values_list(
            'room__room_id',
            flat=True,
        )
        async for member in member_ids:
            if member == client.user_id:
                continue
            # Send alerts to direct messages for now
            their_direct_messages = Event.objects.filter(
                state_key=member,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            room_id = await our_direct_messages.intersection(their_direct_messages).aget()
            if room_id is None:
                continue
            try:
                await client.room_send(
                    room_id=room_id,
                    message_type='m.room.message',
                    content=event.source['content'],
                )
            except nio.LocalProtocolError as e:
                logging.error(''.join(traceback.format_exception(e)))


callbacks = (
    ('alert', alert_callback),
)
