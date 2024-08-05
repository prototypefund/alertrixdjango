import argparse

import nio
from matrixappservice import MatrixClient


async def start(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        args: argparse.Namespace,
):
    return
