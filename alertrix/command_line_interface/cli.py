import inspect
import io
import json
import logging
import shlex
import traceback

import nio
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from matrixappservice import MatrixClient
from matrixappservice import models

from alertrix import callbacks
from .argparse import Parser
from ..models import DirectMessage


async def cli(
        args=None,
        defaults: dict = None,
        override_args: dict = None,
        sender: str = None,
        program_name: str = None,
        client: MatrixClient = None,
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

    account_parser = subparsers.add_parser(
        _('account'),
    )
    account_parser.set_defaults(
        func=callbacks.account.account,
    )
    account_actions = account_parser.add_subparsers(
        parser_class=PC,
        help=_('manage your account'),
    )
    account_create_parser = account_actions.add_parser(
        'create',
        help=_('register'),
    )
    account_create_parser.set_defaults(
        func=callbacks.account.create,
    )

    start_parser = subparsers.add_parser(
        'start',
    )
    start_parser.set_defaults(
        func=callbacks.start.start,
    )

    widget_parser = subparsers.add_parser(
        'widget',
    )
    widget_actions = widget_parser.add_subparsers(
        parser_class=PC,
        help=_('use a widget to access the web interface'),
    )
    widget_create_parser = widget_actions.add_parser('create')
    widget_create_parser.set_defaults(func=callbacks.widget.add_widget_to_chat)

    alert_parser = subparsers.add_parser(
        'alert',
    )
    alert_actions = alert_parser.add_subparsers(
        parser_class=PC,
        help=_('manage alerts'),
    )
    alert_create_parser = alert_actions.add_parser('new')
    alert_create_parser.add_argument(
        'code',
        action='store',
    )
    alert_create_parser.add_argument(
        '-u', '--unit',
        action='append',
        nargs='+',
    )
    alert_create_parser.add_argument(
        '-d', '--description',
        action='store',
    )
    alert_create_parser.add_argument(
        '-a', '--address',
        action='store',
        help=_('postal address'),
    )
    alert_create_parser.add_argument(
        '-l', '--location',
        action='store',
        type=float,
        nargs=2,
        help=_('specify the exact coordinates separated by a comma')
    )
    alert_create_parser.set_defaults(func=callbacks.emergency.alert.add)
    try:
        parsed_args = parser.parse_args(
            args,
        )
    except TypeError:
        return _('invalid command')
    except Exception as e:
        logging.error(''.join(traceback.format_exception(e)))
        return ''.join(type(e).__name__)
    for key, value in defaults.items():
        if not hasattr(parsed_args, key):
            setattr(parsed_args, key, value)
    for key, value in override_args.items():
        setattr(parsed_args, key, value)
    parser.help_print_file.seek(0)
    help_info = parser.help_print_file.read()
    if help_info:
        return help_info
    bot = await models.User.objects.aget(
        user_id=parsed_args.bot,
    )
    client = client or await bot.aget_client()
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
        await client.close()
        return await res
    else:
        await client.close()
        return res


async def chat_cli(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
):
    if event.sender == client.user_id:
        return

    if event.source['content']['msgtype'] != 'm.text':
        return

    try:
        args = shlex.split(event.body)
    except ValueError:
        await process_response(
            client,
            room,
            _('unknown command'),
        )
        return

    # commands either need to be sent to the users direct message with an organisations bot account or be prefixed
    prefix_needed = False
    try:
        dm = await DirectMessage.objects.aget_for(
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

    defaults = {
        'user': event.sender,
    }

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
    response = await cli(
        args=args,
        defaults=defaults,
        override_args=override_args,
        sender=event.sender,
        program_name=program_name,
    )

    if inspect.isgenerator(response):
        for v in response:
            await process_response(
                client,
                room,
                v,
            )
    elif inspect.isasyncgen(response):
        async for v in response:
            await process_response(
                client,
                room,
                v,
            )
    elif type(response) is str:
        for v in [
            response,
        ]:
            await process_response(
                client,
                room,
                v,
            )
    elif response is None:
        pass
    else:
        raise ValueError(
            'unknown response type from callback %(type)s: %(response)s' % {
                'type': type(response),
                'response': response,
            },
        )


async def process_response(
        client: MatrixClient,
        room: nio.MatrixRoom,
        response_text,
):
    if type(response_text) is str:
        content = {
            'msgtype': 'm.notice',
            'body': response_text,
        }
    elif type(response_text) is dict:
        content = response_text
    else:
        content = None
    if content:
        await client.room_send(
            room.room_id,
            'm.room.message',
            content,
            ignore_unverified_devices=True,
        )
