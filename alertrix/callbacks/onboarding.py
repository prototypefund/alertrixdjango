import json
import logging

import nio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from matrixappservice import MatrixClient
from matrixappservice import models as mas_models

from .. import models
from .. import utils
from ..views.alert_channel import CreateAlertChannel


async def on_room_invite(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.InviteMemberEvent,
):
    await prevent_double_direct_messages(
        client,
        room,
        event,
    )
    if not await mas_models.Room.objects.filter(
        room_id=room.room_id,
    ).aexists():
        await mas_models.Room.objects.acreate(
            room_id=room.room_id,
        )
    if event.state_key != client.user_id:
        return
    if event.membership == 'invite':
        await client.join(
            room.room_id,
        )
    if event.content.get('is_direct', False):
        try:
            # Check if there already is a direct message room for this combination of users…
            our_direct_messages = mas_models.Event.objects.filter(
                state_key=client.user_id,
                unsigned__prev_content__is_direct=True,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            their_direct_messages = mas_models.Event.objects.filter(
                state_key=event.sender,
                unsigned__prev_content__is_direct=True,
                content__membership='join',
            ).values_list(
                'room__room_id',
                flat=True,
            )
            dm = await mas_models.Room.objects.aget(
                room_id__in=await our_direct_messages.intersection(their_direct_messages).aget(),
                room_is__ne=room.room_id,
            )
            # … direct the user to that room …
            await client.room_send(
                room_id=room.room_id,
                message_type='m.room.message',
                content={
                    'msgtype': 'm.text',
                    'body': 'https://matrix.to/#/%(room_id)s' % {
                        'room_id': dm.matrix_room_id,
                    },
                }
            )
            # … and leave this room.
            await client.room_leave(
                room.room_id,
            )
            await client.room_forget(
                room.room_id,
            )
            return
        except mas_models.Event.DoesNotExist:
            pass
        await client.room_send(
            room.room_id,
            'm.room.message',
            {
                'msgtype': 'm.text',
                'body': _('welcome to %(service_name)s') % {
                    'service_name': settings.SERVICE_NAME,
                },
            },
        )


async def prevent_double_direct_messages(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    dms = await sync_to_async(list)(models.DirectMessage.objects.get_all_for(
        client.user_id,
        event.sender,
        valid_memberships=[
            'join',
            'invite',
        ],
    ))
    for dm in dms:
        if dm.room_id == room.room_id:
            continue
        try:
            await client.room_send(
                dm.room_id,
                'm.room.message',
                {
                    'msgtype': 'm.notice',
                    'body': _('please use https://matrix.to/#/%(room_id)s from now on') % {
                        'room_id': room.room_id,
                    },
                },
            )
        except (
                ValueError,
        ):
            pass
        await client.room_leave(
            dm.room_id,
        )
        await client.room_forget(
            dm.room_id,
        )
        await dm.adelete()
    await client.sync_n(
        n=1,
    )


async def on_room_join(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    dms = models.DirectMessage.objects.get_all_for(
        client.user_id,
        event.sender,
        valid_memberships=[
            'join',
            'invite',
        ],
    )
    if all([
        await dms.acount() > 1,
        room.room_id in await sync_to_async(list)(dms.values_list(
            'room_id',
        )),
    ]):
        await prevent_double_direct_messages(
            client,
            room,
            event,
        )

    if event.membership != 'join':
        return
    if await models.Company.objects.filter(
            room_id=room.room_id,
    ).aexists():
        await on_user_joined_company(
            client,
            room,
            event,
        )


async def on_user_joined_company(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    try:
        try:
            dm = await models.DirectMessage.objects.aget_for(
                event.sender,
                client.user_id,
            )
        except mas_models.Room.DoesNotExist:
            # Try again, maybe the user has not joined the direct message yet
            dm = await models.DirectMessage.objects.aget_for(
                event.sender,
                client.user_id,
                valid_memberships=[
                    'invite',
                    'join',
                ],
            )
    except mas_models.Room.DoesNotExist:
        # There is no direct message for this user and us yet, so we need to create one.
        room_create_response = await client.room_create(
            preset=nio.RoomPreset.trusted_private_chat,
            invite=[
                event.sender,
            ],
            is_direct=True,
            initial_state=[
                nio.EnableEncryptionBuilder().as_dict(),
            ],
        )
        await client.sync_n(
            n=1,
        )
        if type(room_create_response) is nio.RoomCreateError:
            logging.error(room_create_response)
        dm = await models.DirectMessage.objects.aget(
            room_id=room_create_response.room_id,
        )
    put_state_response = await client.room_put_state(
        room.room_id,
        event_type='m.space.child',
        state_key=dm.room_id,
        content={
            'via': await sync_to_async(list)(
                mas_models.User.objects.filter(
                    user_id__in=models.Event.objects.filter(
                        type='m.room.member',
                        content__membership__in=[
                            'invite',
                            'join',
                        ],
                        room__room_id__in=room.room_id,
                    ),
                ).values_list(
                    'homeserver__server_name',
                    flat=True,
                ),
            ),
        },
    )
    alert_channels = await models.AlertChannel.objects.aget_for(
        event.sender,
        client.user_id,
        valid_memberships=[
            'join',
            'invite',
        ],
    )
    view = CreateAlertChannel()
    pattern = view.form_class.declared_fields['pattern'].initial
    request = utils.get_request(
        POST={
            'name': (
                _('%(pattern)s alerts for %(company_name)s') % {
                    'pattern': pattern,
                    'company_name': (
                        await (
                            await models.Company.objects.aget(
                                room_id=room.room_id,
                            )
                        ).aget_name()
                    ).content['name'],
                }
            ).strip(),
            'company': room.room_id,
            'pattern': pattern,
            'overwrite': 'on',
        },
        META={
            'HTTP_ACCEPT': 'application/json',
        },
        user=await get_user_model().objects.aget(matrix_id=event.sender),
    )
    view.request = request
    if all([
            (await alert_channels.acount()) == 0,
            await sync_to_async(view.has_permission)(),
    ]):
        form = await sync_to_async(view.get_form)()
        if not await sync_to_async(form.is_valid)():
            return
        response = await sync_to_async(view.post)(
            request,
        )

        response_data = json.loads(
            response.content,
        )
        await client.room_send(
            dm.room_id,
            'm.room.message',
            {
                'msgtype': 'm.text',
                'body': _('alerts with a code matching "%(pattern)s" will be sent to %(room)s') % {
                    'pattern': '',
                    'room': 'https://matrix.to/#/%(room_id)s' % {
                        'room_id': response_data['room_id'],
                    },
                },
            },
        )


async def ensure_encryption(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMessage,
):
    if not settings.ALERTRIX_ENFORCE_ENCRYPTION:
        # This alertrix instance does not enforce encryption
        return
    if client.rooms[room.room_id].encrypted:
        # This room already is encrypted
        return
    if event.source['content'].get('net.alertrix.request_encryption') is not None:
        # This request likely comes from us or another alertrix bot
        return
    enable_encryption_event = nio.EnableEncryptionBuilder().as_dict()
    room_put_state_response = await client.room_put_state(
        room_id=room.room_id,
        event_type=enable_encryption_event.pop('type'),
        **enable_encryption_event,
    )
    if type(room_put_state_response) is nio.RoomPutStateError:
        await client.room_send(
            room_id=room.room_id,
            message_type='m.room.message',
            content={
                'net.alertrix.request_encryption': '',
                'msgtype': 'm.notice',
                'body': _('please enable encryption'),
            }
        )
