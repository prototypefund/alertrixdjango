import nio
from matrixappservice import MatrixClient

from .. import models


async def on_left_direct_message(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    if event.membership != 'leave':
        return
    try:
        dm: models.DirectMessage = await models.DirectMessage.objects.aget(
            matrix_room_id=room.room_id,
        )
    except models.DirectMessage.DoesNotExist:
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
