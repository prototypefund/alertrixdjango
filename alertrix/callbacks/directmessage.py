import nio
from matrixappservice import MatrixClient
from matrixappservice import models

from .. import querysets
from .. import models


async def on_left_direct_message(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    if event.membership != 'leave':
        return
    if not await models.DirectMessage.objects.filter(
            room_id=room.room_id,
    ).aexists():
        # This room does not seem to be a direct message
        return
    try:
        dm: models.Room = await models.DirectMessage.objects.aget_for(
            event.sender,
            client.user_id,
        )
    except models.Room.DoesNotExist:
        return
    if await models.Event.objects.filter(
        room=dm,
        type='m.room.membership',
        content__membership='join',
    ).acount() > 1:
        return
    await client.room_leave(
        room.room_id,
    )
    await client.room_forget(
        room.room_id,
    )
    await models.Room.objects.get(
        room_id=room.room_id,
    ).adelete()
