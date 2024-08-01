import inspect
import io
import json
import logging
import traceback

import nio
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from matrixappservice import models

from .argparse import Parser


async def cli(
        args=None,
        override_args: dict = None,
        sender: str = None,
        program_name: str = None,
):
    output_file = io.StringIO()

    class PC(
        Parser,
    ):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Make the parser write its output to this in-memory file
            self.help_print_file = output_file

    parser = PC(
        program_name or getattr(settings, 'ALERTRIX_COMMAND_PREFIX') or '',
    )
    subparsers = parser.add_subparsers(
        title='commands',
        help=_('these are the commands you can execute'),
    )

    try:
        user = await get_user_model().objects.aget(
            matrix_id=sender,
        )
    except get_user_model().DoesNotExist:
        user = None

    try:
        parsed_args = parser.parse_args(
            args,
        )
    except TypeError:
        return _('invalid command')
    except Exception as e:
        logging.error(''.join(traceback.format_exception(e)))
        return ''.join(type(e).__name__)
    for key, value in override_args.items():
        setattr(parsed_args, key, value)
    parser.help_print_file.seek(0)
    help_info = parser.help_print_file.read()
    if help_info:
        return help_info
    bot = await models.User.objects.aget(
        user_id=parsed_args.bot,
    )
    client = await bot.aget_client()
    room = await models.Room.objects.aget(
        room_id=parsed_args.room
    )
    if room.room_id not in client.rooms:
        client.rooms[room.room_id] = await room.aget_nio_room(bot.user_id)
    try:
        callback = parsed_args.func
    except AttributeError:
        return NotImplementedError.__name__
    callback_args = [
        client,
        client.rooms[room.room_id],
        nio.Event(json.loads(parsed_args.event)),
    ]
    res = callback(
        *callback_args,
    )
    if inspect.isawaitable(res):
        return await res
    else:
        return res
