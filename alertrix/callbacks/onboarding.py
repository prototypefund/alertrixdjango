import json
import logging

import nio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from matrixappservice import MatrixClient
from matrixappservice import models as mas_models



async def on_room_invite(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.InviteMemberEvent,
):
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
                body={
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


async def on_room_join(
        client: MatrixClient,
        room: nio.MatrixRoom,
        event: nio.RoomMemberEvent,
):
    if event.membership != 'join':
        return
    if await querysets.companies.filter(
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
        await querysets.aget_direct_message_for(
            event.sender,
            client.user_id,
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
        if type(room_create_response) is nio.RoomCreateError:
            logging.error(room_create_response)


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
