from unittest import IsolatedAsyncioTestCase
from urllib.parse import urlencode

import nio
import time
from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import AsyncClient
from django.urls import reverse
from matrixappservice import models as mas_models

from . import callbacks
from . import models
from .events import v1 as events
from .test import AppserviceSetup


class MatrixRoomTest(
    AppserviceSetup,
    IsolatedAsyncioTestCase
):
    """
    Test managing companies and units
    """

    async def test_create_organisation_and_unit(self):
        # Create a Matrix-Account for the test user in the scope of the application service
        mx_user, new = await mas_models.User.objects.aget_or_create(
            user_id='@alertrix_OrganisationTest_test_create_organisation_and_unit-user:synapse',
            app_service=self.app_service,
            prevent_automated_responses=True,
        )
        main_app_service_key = await models.MainApplicationServiceKey.objects.aget()
        main_user_key = await models.MainUserKey.objects.aget(
            service=await sync_to_async(getattr)(main_app_service_key, 'service'),
        )
        main_user: mas_models.User = await sync_to_async(getattr)(main_user_key, 'user')

        messages = {}

        def store_messages(c, r, e):
            if c.user_id not in messages:
                messages[c.user_id] = []
            messages[c.user_id].append([r, e])

        mx_client = await mx_user.aget_client()
        mx_client.add_event_callback(
            store_messages,
            nio.Event,
        )
        mx_client.add_event_callback(
            callbacks.encryption.verify_all_devices,
            nio.RoomMessage,
        )
        mx_client.add_event_callback(
            callbacks.encryption.verify_all_devices,
            nio.RoomMemberEvent,
        )
        mx_client.add_event_callback(
            lambda c, r, e: c.join(r.room_id),
            nio.InviteMemberEvent,
        )

        room_create_response = await mx_client.room_create(
            preset=nio.RoomPreset.trusted_private_chat,
            invite=(
                main_user.user_id,
            ),
            is_direct=True,
            initial_state=[
                nio.EnableEncryptionBuilder().as_dict(),
            ],
        )
        if type(room_create_response) is nio.RoomCreateError:
            self.fail(
                'unable to create room as user %(user_id)s: %(errcode)s %(errmsg)s' % {
                    'user_id': mx_client.user_id,
                    'errcode': room_create_response.status_code,
                    'errmsg': room_create_response.message,
                },
            )
        await mx_client.sync_n(
            n=1,
        )
        start = time.time()
        end = start + 20
        memberships = (
            ('join', mx_client.user_id),
            ('join', main_user.user_id),
        )
        # waiting for bot to join
        while time.time() < end:
            if all([
                await mas_models.Event.objects.filter(
                    room__room_id=room_create_response.room_id,
                    type='m.room.member',
                    content__membership=membership[0],
                    state_key=membership[1],
                ).aexists()
                for membership in memberships
            ]):
                break
            await mx_client.sync_n(
                n=1,
            )
        else:
            self.fail(
                'memberships of direct message are incorrect',
            )
        await sync_to_async(self.assertIn)(
            ('join', mx_client.user_id),
            mas_models.Event.objects.filter(
                room__room_id=room_create_response.room_id,
                type='m.room.member',
            ).values_list(
                'content__membership', 'state_key',
            ),
        )
        await sync_to_async(self.assertIn)(
            ('join', main_user.user_id),
            mas_models.Event.objects.filter(
                room__room_id=room_create_response.room_id,
                type='m.room.member',
            ).values_list(
                'content__membership', 'state_key',
            ),
        )
        await mx_client.sync_n(
            n=1,
        )
        await mx_client.room_send(
            room_create_response.room_id,
            'm.room.message',
            {
                'msgtype': 'm.text',
                'body': 'start',
            },
        )
        await mx_client.sync_n(
            n=1,
        )
        start = time.time()
        end = start + 2
        while time.time() < end:
            if await mas_models.Event.objects.filter(
                    room__room_id=room_create_response.room_id,
                    type='im.vector.modular.widgets',
            ).aexists():
                break
        else:
            self.fail(
                'did not receive widget event in time',
            )
        widget_event = await mas_models.Event.objects.aget(
            room__room_id=room_create_response.room_id,
            type='im.vector.modular.widgets',
        )
        url = widget_event.content['url']
        client = AsyncClient()
        # Do not allow every user to access the company creation form
        resp = await client.get(
            reverse('comp.new'),
        )
        self.assertEqual(
            resp.status_code,
            302,
        )
        # The activation secret is only set once the widget is used for the first time
        widget_activation_response = await client.get(
            url,
        )
        widget_activation_page = widget_activation_response.content.decode()
        widget_activation = BeautifulSoup(widget_activation_page, 'html.parser')
        input_tag_id = widget_activation.find(
            'input',
            attrs={
                'name': 'id',
            },
        )
        await mx_client.sync_n(
            n=1,
        )
        widget_activation_event = messages[mx_client.user_id][-1][1]
        self.assertIn(
            'activation_secret',
            widget_activation_event.source['content'].keys(),
            'activation secret has not been received or was not saved',
        )
        resp = await client.post(
            url,
            data=urlencode({
                'id': input_tag_id['value'],
                'activation_secret': widget_activation_event.source['content']['activation_secret'],
            }),
            content_type='application/x-www-form-urlencoded',
        )
        user = await get_user_model().objects.aget(
            matrix_id=mx_client.user_id,
        )
        self.assertGreater(
            await user.groups.acount(),
            0,
            'user is not part of any group',
        )
        # Allow access to the company creation form now
        resp = await client.get(
            reverse('comp.new'),
        )
        self.assertEqual(
            resp.status_code,
            200,
        )
        company_initial_data = {
            'name': 'OrganisationTest test create organisation and unit Company',
            'description': 'Hello World!',
            'application_service': self.app_service.pk,
        }
        resp = await client.post(
            reverse('comp.new'),
            data=company_initial_data,
        )
        self.assertEqual(
            resp.status_code,
            302,
        )
        await mx_client.sync_n(
            n=1,
        )
        company = await models.Company.objects.aget(
            room_id__in=mas_models.Event.objects.filter(
                type='m.room.name',
                content__name=company_initial_data['name'],
            ).values_list(
                'room__room_id',
                flat=True,
            ),
        )
        # Wait for an invitation to the company space
        start = time.time()
        end = start + 10
        while time.time() < end:
            room_ids = await sync_to_async(list)(
                mas_models.Room.objects.filter(
                    room_id__in=mas_models.Event.objects.filter(
                        type='m.room.member',
                        state_key=mx_client.user_id,
                        content__membership='join',
                    ).values_list(
                        'room__room_id',
                        flat=True,
                    ),
                ).values_list(
                    'room_id',
                    flat=True,
                ),
            )
            if company.room_id in room_ids:
                break
        else:
            self.fail(
                'User has not received an invite to a room with the correct name in time',
            )
        resp = await client.get(
            reverse('unit.new'),
        )
        self.assertEqual(
            resp.status_code,
            200,
        )
        unit_initial_data = {
            'name': 'OrganisationTest test create organisation and unit Unit',
            'description': 'Hello, World!',
            'companies': [
                company.room_id,
            ],
        }
        resp = await client.post(
            reverse('unit.new'),
            data=unit_initial_data,
        )
        self.assertEqual(
            resp.status_code,
            302,
        )
        await mx_client.sync_n(
            n=1,
        )
        units = models.Unit.objects.filter(
            room_id__in=mas_models.Event.objects.filter(
                type='m.room.name',
                content__name=unit_initial_data['name'],
            ).values_list(
                'room__room_id',
                flat=True,
            ),
        )
        unit = await units.aget()
        # Wait for an invitation to the unit space
        start = time.time()
        end = start + 10
        while time.time() < end:
            room_ids = await sync_to_async(list)(
                mas_models.Event.objects.filter(
                    type='m.room.member',
                    state_key=mx_client.user_id,
                    content__membership='join',
                ).values_list(
                    'room__room_id',
                    flat=True,
                ).distinct(
                ),
            )
            if unit.room_id in room_ids:
                break
        else:
            self.fail(
                'User has not received an invite to a room with the correct name in time',
            )

        # After joining the company the user should have been invited to a direct message that is used for non-alert
        # notifications and configuration
        config_dm = await models.DirectMessage.objects.aget_for(
            user.matrix_id,
            (await mas_models.Event.objects.aget(
                type=events.AlertrixCompany().type,
                room=company,
                state_key='',
            )).content['inbox'],
        )
        config_dm_test_message = {
            'msgtype': 'm.text',
            'body': '--help',
        }
        await mx_client.room_send(
            config_dm.room_id,
            'm.room.message',
            config_dm_test_message,
            ignore_unverified_devices=True,
        )

        alert_channels = await models.AlertChannel.objects.aget_for(
            mx_client.user_id,
            (await models.Event.objects.aget(
                room=company,
                type=events.AlertrixCompany.get_type(),
            )).content['inbox'],
        )
        self.assertEqual(
            await alert_channels.acount(),
            1,
        )
        await mx_client.close()
