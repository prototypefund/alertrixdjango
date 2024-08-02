import inspect
import io
import json
import logging
import traceback

import nio
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient
from matrixappservice import models

from .argparse import Parser
from .. import querysets


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
        program_name or getattr(settings, 'ALERTRIX_COMMAND_NAME') or '',
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
    if callback.__code__.co_argcount > len(callback_args):
        callback_args.append(parsed_args)
    res = callback(
        *callback_args,
    )
    if inspect.isawaitable(res):
        return await res
    else:
        return res


async def chat_cli(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
):
    if event.sender == client.user_id:
        return

    args = event.body.split()

    # commands either need to be sent to the users direct message with an organisations bot account or be prefixed
    prefix_needed = False
    try:
        dm = await querysets.aget_direct_message_for(
            event.sender,
            client.user_id,
        )
        if dm.room_id != room.room_id:
            prefix_needed = True
    except models.Room.DoesNotExist:
        # No direct message set up for this user, so this chat cannot be a direct message
        prefix_needed = True,
    prefix = getattr(settings, 'ALERTRIX_COMMAND_PREFIX') or '!'
    program_name = getattr(settings, 'ALERTRIX_COMMAND_NAME') or 'alertrix'
    if prefix_needed:
        if args[0] != prefix + (program_name or ''):
            # This command is not meant for us
            return
        args.pop(0)
    else:
        if args[0] == prefix + (program_name or ''):
            # The request includes the command prefix and name, so we remove them
            args.pop(0)

    # Since this is the chat interface we do not want the user to have access to everything
    override_args = {
        'event': json.dumps(event.source),  # do not allow passing custom events
        'room': room.room_id,  # do not allow acting in other rooms
        'bot': client.user_id,  # do not allow the use of another bot
    }
    # prevent impersonating for non-admins
    try:
        user = await get_user_model().objects.aget(
            matrix_id=event.sender,
        )
    except get_user_model().DoesNotExist:
        user = None
    if user is None or not user.is_superuser:
        override_args['user'] = event.sender

    # call the command line interface function
    response_text = await cli(
        args=args,
        override_args=override_args,
        sender=event.sender,
        program_name=program_name,
    )
    if type(response_text) is str:
        content = {
            'msgtype': 'm.text',
            'body': response_text,
        }
    elif type(response_text) is dict:
        content = response_text
    else:
        content = None
    if response_text:
        await client.room_send(
            room.room_id,
            'm.room.message',
            content,
            ignore_unverified_devices=True,
        )
