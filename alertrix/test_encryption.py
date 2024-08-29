import secrets
import string
from unittest import IsolatedAsyncioTestCase

import nio
from asgiref.sync import sync_to_async
from matrixappservice import MatrixClient
from matrixappservice import models

from . import test


class EncryptionTests(
    test.AppserviceSetup,
    IsolatedAsyncioTestCase,
):
    """
    Test aspects of encryped matrix communication for alertrix.
    """

    async def test_e2ee_messaging(self):
        user1 = await models.User.objects.acreate(
            user_id='@alertrix_EncryptionTest_test_e2ee_messaging_user1:synapse.localhost',
            app_service=self.app_service,
            homeserver=self.homeserver,
        )
        user2 = await models.User.objects.acreate(
            user_id='@alertrix_EncryptionTest_test_e2ee_messaging_user2:synapse.localhost',
            app_service=self.app_service,
            homeserver=self.homeserver,
        )
        client1: MatrixClient = await user1.aget_client()
        client2: MatrixClient = await user2.aget_client()
        await client1.sync_n(
            n=3,
            timeout=1,
        )
        await client2.sync_n(
            n=3,
            timeout=1,
        )
        received_events = {
            client1.user_id: [],
            client2.user_id: [],
        }

        def receive_event(c, r, e):
            if e.sender == c.user_id:
                # we sent this message ourselves
                return
            received_events[c.user_id].append(
                [r.room_id, e.source],
            )

        client1.add_event_callback(receive_event, nio.RoomMessageText)
        client2.add_event_callback(receive_event, nio.RoomMessageText)
        room_create_response = await client1.room_create(
            invite=[
                client2.user_id,
            ],
            initial_state=[
                nio.EnableEncryptionBuilder().as_dict(),
            ],
        )
        room_join_response = await client2.join(
            room_create_response.room_id,
        )
        await client1.sync_n(
            n=3,
            timeout=1,
        )
        await client2.sync_n(
            n=3,
            timeout=1,
        )
        room = models.Room(
            room_id=room_join_response.room_id,
        )
        client1.rooms[room_join_response.room_id] = await room.aget_nio_room(
            client1.user_id,
        )
        client2.rooms[room_join_response.room_id] = await room.aget_nio_room(
            client2.user_id,
        )
        for client, other_client in [
            [client1, client2],
            [client2, client1],
        ]:
            for device_id, device in client.device_store[other_client.user_id].items():
                await sync_to_async(client.verify_device)(
                    device,
                )
        message_body = ''.join([secrets.choice(string.printable) for _ in range(16)])
        room_send_response = await client1.room_send(
            room_create_response.room_id,
            'm.room.message',
            {
                'msgtype': 'm.text',
                'body': message_body,
            },
        )
        self.assertIs(
            type(room_send_response),
            nio.RoomSendResponse,
            'Sending a message to the room failed',
        )
        await client1.sync_n(
            n=3,
            timeout=1,
        )
        await client2.sync_n(
            n=3,
            timeout=1,
        )
        self.assertEqual(
            message_body,
            received_events[client2.user_id][0][1]['content']['body'],
            'message not received or decrypted',
        )
        await client1.close()
        await client2.close()
        del client1
        del client2
