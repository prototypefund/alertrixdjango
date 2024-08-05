import argparse

import nio
from django.contrib.auth import get_user_model
from matrixappservice import MatrixClient
from .. import account
from .. import widget


async def start(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        args: argparse.Namespace,
):
    # Register the user if they did not do so earlier
    if not await get_user_model().objects.filter(
        matrix_id=event.sender,
    ).aexists():
        await account.create(
            client,
            room,
            event,
            args,
        )
    # Set up graphical interface/widget for them
    await widget.add_widget_to_chat(
        client,
        room,
        event,
        args,
    )
    return
