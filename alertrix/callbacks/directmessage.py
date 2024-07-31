import nio
from matrixappservice import MatrixClient
from matrixappservice import models

from .. import querysets


async def on_left_direct_message(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    if event.membership != 'leave':
        return
    try:
        dm: models.Room = await querysets.aget_direct_message_for(
            event.sender,
            client.user_id,
        )
    except models.Room.DoesNotExist:
        # This room does not seem to be a direct message
        return
    if dm.with_user.matrix_id != event.sender:
        # Somebody other than the person this dm if set up for left the room
        return
    await client.room_leave(
        room.room_id,
    )
    await client.room_forget(
        room.room_id,
    )
    await dm.adelete()
