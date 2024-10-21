import logging
import os

import nio
from asgiref.sync import sync_to_async
from matrixappservice import MatrixClient

logger = logging.getLogger(__name__)
log_separator = '__'
log_id_prefix = 'LOG'
var_name = '%s%s%s' % (log_id_prefix, log_separator, __name__.upper().replace('.', log_separator))
while True:
    if os.getenv(var_name) is not None or var_name == 'LOG':
        break
    var_name = log_separator.join(var_name.split(log_separator)[:-1])
logger.setLevel(os.getenv(var_name, '').upper() or logger.getEffectiveLevel())
logger.addHandler(logging.StreamHandler())


async def verify_all_devices(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    for device_id, device in client.device_store[event.sender].items():
        await sync_to_async(client.verify_device)(
            device,
        )
