from unittest import IsolatedAsyncioTestCase

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.test import AsyncClient
from django.urls import reverse
from matrixappservice import models as mas_models

from . import models
from .test import AppserviceSetup


class MatrixRoomTest(
    AppserviceSetup,
    IsolatedAsyncioTestCase
):
    """
    Test managing companies and units
    """

    async def test_create_organisation_and_unit(self):
        user, new = await get_user_model().objects.aget_or_create(
            matrix_id='@alertrix_OrganisationTest_test_create_organisation_and_unit:synapse.localhost',
        )
        # Create a Matrix-Account for the test user in the scope of the application service
        mx_user, new = await mas_models.User.objects.aget_or_create(
            user_id=user.matrix_id,
            app_service=self.app_service,
        )
        mx_client = await mx_user.aget_client()
        client = AsyncClient()
        await client.aforce_login(user)
        # Do not allow every user to access the company creation form
        resp = await client.get(
            reverse('comp.new'),
        )
        self.assertEqual(
            resp.status_code,
            403,
        )
        await sync_to_async(self.validated_matrix_id_group.user_set.add)(user)
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
        # since we have the special case of managing the users matrix account using the application service, they
        # already joined the room
        company = await models.Company.objects.aget(
            room_id__in=mas_models.Event.objects.filter(
                type='m.room.name',
                content__name=company_initial_data['name'],
            ).values_list(
                'room__room_id',
                flat=True,
            ),
        )
        self.assertEqual(
            company.room_id,
            (
                await mas_models.Room.objects.aget(
                    room_id__in=mas_models.Event.objects.filter(
                        type='m.room.member',
                        state_key=user.matrix_id,
                        content__membership='join',
                    ).values_list(
                        'room__room_id',
                        flat=True,
                    ),
                )
            ).room_id,
            'User has not received an invite to a room with the correct name',
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
        # since we have the special case of managing the users matrix account using the application service, they
        # already joined the room
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
        self.assertIn(
            unit.room_id,
            await sync_to_async(list)(
                mas_models.Event.objects.filter(
                    type='m.room.member',
                    state_key=user.matrix_id,
                    content__membership='join',
                ).values_list(
                    'room__room_id',
                    flat=True,
                ).distinct(
                ),
            ),
            'User has not received an invite to a room with the correct name',
        )
