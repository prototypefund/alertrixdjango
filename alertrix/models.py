import logging
import traceback

import matrixappservice.exceptions
import nio
from django.http import HttpResponse
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.utils import timezone

from matrixappservice import exceptions as exc
from matrixappservice.handler import Handler as ApplicationServiceHandler
from matrixappservice.matrix.action import MatrixAction
from matrixappservice.models import ApplicationServiceRegistration
from matrixappservice.models import Homeserver
from matrixappservice.models import User as MatrixUser
from django.contrib.auth import get_user_model


class User(
    AbstractUser,
):
    USERNAME_FIELD = 'matrix_id'
    username = None
    matrix_id = models.TextField(
        'Matrix ID',
        primary_key=True,
        help_text='@user:example.com',
    )

    def __str__(self):
        return str(self.__getattribute__(self.USERNAME_FIELD))


class Handler(
    models.Model,
    ApplicationServiceHandler,
):
    application_service = models.OneToOneField(
        ApplicationServiceRegistration,
        on_delete=models.CASCADE,
    )
    users = models.ForeignKey(
        Group,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )

    async def on_query_user(
            self,
            request,
            user_id,
    ):
        try:
            user = await MatrixUser.objects.aget(
                user_id=user_id,
            )
        except MatrixUser.DoesNotExist:
            user = MatrixUser(
                user_id,
                homeserver=await sync_to_async(self.app_service.__getattribute__)('homeserver'),
                app_service=self.app_service,
            )
            await user.register()

    async def on_m_room_message(
            self,
            request,
            event,
    ):
        app_service = await sync_to_async(self.__getattribute__)('application_service')
        as_client: nio.AsyncClient = await app_service.get_matrix_client()
        joined_members_resp = await as_client.joined_members(
            event['room_id'],
        )
        members = [
            str(member.user_id)
            for member in joined_members_resp.members
        ]
        user: MatrixUser = await MatrixUser.objects.filter(
            user_id__in=members,
        ).afirst()
        try:
            room = await MatrixRoom.objects.aget(
                matrix_room_id=event['room_id'],
            )
        except MatrixRoom.DoesNotExist:
            yield HttpResponse(
                str(matrixappservice.exceptions.MNotFOUND(
                    'This room could not be found',
                )),
            )
            return
        device = await user.device_set.afirst()
        client = await user.get_client()
        if event['type'] == 'm.room.message' and event['content']['body'] == 'ping':
            yield MatrixAction(
                client=client,
                args=nio.Api.room_send(
                    access_token=device.access_token,
                    room_id=event['room_id'],
                    event_type='m.room.message',
                    body={
                        'body': 'pong',
                        'msgtype': 'm.text',
                    },
                    tx_id=device.latest_transaction_id,
                ),
            )
            device.latest_transaction_id += 1
            await device.asave()
        if event['type'] == 'm.room.message' and event['content']['body'].lower().split(' ')[0] == 'start':
            # Create the widget
            room_id = event['room_id']
            event_type = 'im.vector.modular.widgets'
            content = {
                'type': 'm.custom',
                'url': request.META['HTTP_X_FORWARDED_PROTO'] + '://' + request.get_host(),
                'name': request.get_host(),
                'data': {
                },
            }
            widget_id = '%(room)s_%(user)s_%(tms)s' % {
                'room': slugify(room_id),
                'user': slugify(event['sender']),
                'tms': int(timezone.now().timestamp()),
            }
            widget = Widget(
                id=widget_id,
                room=room,
                user_id=event['sender'],
            )
            await widget.asave()
            widget_create_action = MatrixAction(
                client=client,
                args=nio.Api.room_put_state(
                    access_token=client.access_token,
                    room_id=room_id,
                    event_type=event_type,
                    body=content,
                    state_key=widget_id,
                ),
            )
            yield widget_create_action
            device.latest_transaction_id += 1
            # Set the room layout
            await device.asave()
            content = {
                'widgets': {
                    widget_id: {
                        'container': 'top',
                    },
                },
            }
            yield MatrixAction(
                client=client,
                args=nio.Api.room_put_state(
                    access_token=client.access_token,
                    room_id=room_id,
                    event_type='io.element.widgets.layout',
                    body=content,
                    state_key='',
                ),
            )
            device.latest_transaction_id += 1
            await device.asave()
        await client.close()

    async def on_im_vector_modular_widgets(
            self,
            request,
            event,
    ):
        """
        React to im.vector.modular.widgets events
        """
        if event['content'] == {}:
            widget_id = event['state_key']
            try:
                widget = await Widget.objects.aget(id=widget_id)
                if event['room_id'] != widget.room_id:
                    raise PermissionError(
                        matrixappservice.exceptions.MInvalidParam(
                            'Widget should not exist in this room.',
                        ),
                    )
                await widget.adelete()
            except Widget.DoesNotExist:
                return HttpResponse(
                    str(matrixappservice.exceptions.MNotFOUND()),
                )

    async def on_room_invite(
            self,
            request,
            event,
            user: MatrixUser,
    ):
        async for matrix_action in ApplicationServiceHandler.on_room_invite(
            self,
            request,
            event,
            user,
        ):
            yield matrix_action
        client: nio.AsyncClient = await user.get_client()
        if 'is_direct' in event['content'] and event['content']['is_direct']:
            # This room is a direct messaging room
            person, new = await sync_to_async(get_user_model().objects.get_or_create)(
                matrix_id=event['sender'],
            )
            if new:
                group, group_new = await Group.objects.aget_or_create(
                    name=settings.MATRIX_VALIDATED_GROUP_NAME,
                )
                if group_new:
                    await group.asave()
                await sync_to_async(group.user_set.add)(
                    person,
                )
                person.set_unusable_password()
                await person.asave()
            dm = DirectMessage(
                with_user=person,
                matrix_room_id=event['room_id'],
                responsible_user=user,
            )
            await dm.asave()
        device = await user.get_device()

    def __str__(self):
        return str(self.application_service)


class MatrixRoom(
    models.Model,
):
    matrix_room_id = models.TextField(
        primary_key=True,
    )
    responsible_user = models.ForeignKey(
        MatrixUser,
        verbose_name=_('responsible user'),
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )

    async def aget_room_info(
            self,
    ):
        mx_user = await sync_to_async(self.__getattribute__)('responsible_user')
        if mx_user is None:
            return []
        client: nio.AsyncClient = await mx_user.get_client()
        room_info = await client.room_get_state(
            str(self.matrix_room_id),
        )
        if type(room_info) is nio.RoomGetStateError:
            logging.error(
                room_info,
            )
            return []
        return room_info.events

    def get_room_info(
            self,
    ):
        return async_to_sync(self.aget_room_info)()

    async def aget_room_state_event(
            self,
            event_type: str,
            state_key: str = None,
    ):
        mx_user = await sync_to_async(self.__getattribute__)('responsible_user')
        if mx_user is None:
            return {}
        client: nio.AsyncClient = await mx_user.get_client()
        event = await client.room_get_state_event(
            room_id=str(self.matrix_room_id),
            event_type=event_type,
            state_key=state_key or '',
        )
        if type(event) == nio.RoomGetStateEventError:
            return None
        if 'errcode' in event.content:
            e = exc.MatrixError(
                event.content['error'],
            )
            e.errcode = event.content['errcode']
            raise e
        return event.content

    def get_room_state_event(
            self,
            event_type: str,
            state_key: str = None,
    ):
        return async_to_sync(self.aget_room_state_event)(
            event_type=event_type,
            state_key=state_key,
        )

    async def aget_room_avatar(
            self,
    ):
        room_id = str(self.matrix_room_id)
        try:
            state_event = await self.aget_room_state_event(
                event_type='m.room.avatar',
            )
            if state_event is None:
                return ''
        except exc.MatrixError:
            return ''
        if 'url' in state_event:
            return state_event['url']
        return ''

    def get_room_avatar(self):
        return async_to_sync(self.aget_room_avatar)()

    def get_attribute(self, key: str):
        for event in self.get_room_info():
            if event['type'] == 'm.room.%(key)s' % {'key': key}:
                return event['content'][key]

    def get_name(self):
        return self.get_attribute('name')

    def get_description(self):
        return self.get_attribute('topic')

    def get_relations(self, relation_type: str):
        children = []
        for state_event in self.get_room_info():
            if state_event['type'] != relation_type:
                continue
            try:
                matrix_room = MatrixRoom.objects.get(
                    matrix_room_id=state_event['state_key'],
                )
            except MatrixRoom.DoesNotExist:
                if state_event['room_id'] == self.matrix_room_id:
                    continue
                matrix_room = MatrixRoom(
                    matrix_room_id=state_event['room_id'],
                )
            children.append(matrix_room)
        return children

    def get_children(self):
        return self.get_relations('m.space.child')

    def get_parents(self):
        return self.get_relations('m.space.parent')

    async def aget_members(self):
        room_info = await self.aget_room_info()
        members = [
            state_event
            for state_event in room_info
            if state_event['type'] == 'm.room.member'
        ]
        return members

    def get_members(self):
        return async_to_sync(self.aget_members)()

    def get_joined_members(self):
        membership_info = self.get_members()
        members = [
            state_event
            for state_event in membership_info
            if state_event['content']['membership'] == 'join'
        ]
        return members

    def get_real_users(self):
        for member in self.get_members():
            user_objects = get_user_model().objects.filter(
                matrix_id=member.user_id,
            )
            if user_objects.exists():
                yield user_objects.first()

    def get_as_users(self):
        """
        Get all users of a room that are controlled by this application service.
        """
        for member in self.get_members():
            user_objects = MatrixUser.objects.filter(
                matrix_id=member.user_id,
            )
            if user_objects.exists():
                yield user_objects.first()

    def __str__(self):
        return self.get_name() or super().__str__()


class DirectMessage(
    MatrixRoom,
):
    with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(self.with_user)


class Company(
    MatrixRoom,
):
    class Meta:
        verbose_name = _('company')
        verbose_name_plural = _('companies')

    slug = models.SlugField(
        _('slug'),
        primary_key=True,
        max_length=settings.ALERTRIX_SLUG_MAX_LENGTH,
    )
    handler = models.ForeignKey(
        Handler,
        verbose_name=_('handler'),
        on_delete=models.DO_NOTHING,
    )
    admins = models.ForeignKey(
        Group,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )


class Unit(
    MatrixRoom,
):
    class Meta:
        verbose_name = _('unit')
        verbose_name_plural = _('units')


class Widget(
    models.Model,
):
    id = models.TextField(
        primary_key=True,
    )
    room = models.ForeignKey(
        MatrixRoom,
        on_delete=models.CASCADE,
    )
    user_id = models.TextField(
    )
    created_timestamp = models.DateTimeField(
        auto_now=True,
    )
    first_use_timestamp = models.DateTimeField(
        default=None,
        blank=True,
        null=True,
    )


class MainApplicationServiceKey(
    models.Model,
):
    service = models.ForeignKey(
        ApplicationServiceRegistration,
        on_delete=models.CASCADE,
    )

    def save(
            self,
            *args, **kwargs
    ):
        self.id = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass
