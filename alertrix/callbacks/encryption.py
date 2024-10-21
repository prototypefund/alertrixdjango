import logging
import nio
from asgiref.sync import sync_to_async
from matrixappservice import MatrixClient


async def verify_all_devices(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    for device_id, device in client.device_store[event.sender].items():
        await sync_to_async(client.verify_device)(
            device,
        )
