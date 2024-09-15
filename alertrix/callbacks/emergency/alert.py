import argparse
from importlib import import_module

import nio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.constants import DEFAULT_TAGS as DEFAULT_MESSAGE_TAGS
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest
from django.template import loader
from matrixappservice import MatrixClient

from ... import utils
from ...views.emergency import AlertView


async def add(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
        args: argparse.Namespace = None,
):
    units = []
    for unit_section in args.unit:
        units += unit_section

    alert_form_dict = dict(
        code=args.code,
        description=args.description,
        units=units,
        address=args.address,
        location_0=args.location[0],
        location_1=args.location[1],
    )

    request = utils.get_request(
        method='POST',
        POST=alert_form_dict,
        user=await get_user_model().objects.aget(matrix_id=args.user),
    )

    view = AlertView()
    view.request = request
    response = await sync_to_async(view.post)(
        request,
    )
    if response.status_code in [
        302,
    ]:
        messages = get_messages(request)
        if messages:
            for message in messages:
                yield {
                    'msgtype': 'm.notice',
                    'body': '%(level)s: %(message)s' % {
                        'level': DEFAULT_MESSAGE_TAGS.get(message.level).upper()
                        if message.level in DEFAULT_MESSAGE_TAGS else
                        message.level,
                        'message': message.message,
                    },
                    'm.relates_to': {
                        'm.in_reply_to': {
                            'event_id': event.event_id,
                        },
                    },
                }
        else:
            yield 'ok'
    else:
        form = await sync_to_async(view.get_form)()
        if form.errors:
            res = loader.render_to_string(
                'alertrix/cli/form_failed.json',
                {
                    'form': form,
                },
            )
            yield res
