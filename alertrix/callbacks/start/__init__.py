import argparse

import nio
from django.contrib.auth import get_user_model
from matrixappservice import MatrixClient


async def start(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        args: argparse.Namespace,
):
    return
