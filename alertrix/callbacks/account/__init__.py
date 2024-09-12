import argparse
import json

import nio
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient
from django.template import loader

from alertrix.accounts.forms import UserCreationForm


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


async def create(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        args: argparse.Namespace,
):
    form = UserCreationForm(
        {
            'matrix_id': args.user,
        },
    )
    if await sync_to_async(form.is_valid)():
        await sync_to_async(form.save)()
    if form.errors:
        res = loader.render_to_string(
            'alertrix/cli/form_failed.json',
            {
                'form': form,
            },
        )
        return json.loads(res)
    return _('user created')
