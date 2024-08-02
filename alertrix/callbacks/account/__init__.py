import argparse
import json
import nio
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from matrixappservice import MatrixClient
from django.template import loader


async def account(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        args: argparse.Namespace,
):
    try:
        user = await get_user_model().objects.aget(matrix_id=args.user or event.sender)
        description_str = loader.render_to_string(
            'alertrix/cli/user_detail.json',
            {
                'user': user,
            },
        )
        description = json.loads(description_str)
    except get_user_model().DoesNotExist:
        description = AnonymousUser.__name__
    return description
