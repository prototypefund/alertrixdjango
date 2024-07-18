import logging
import traceback
import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import gettext_lazy as _

from matrixappservice import exceptions as exc
from matrixappservice.models import ApplicationServiceRegistration
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
        client: nio.AsyncClient = await mx_user.aget_client()
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
        client: nio.AsyncClient = await mx_user.aget_client()
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

    def delete(self, using=None, keep_parents=False):
        async_to_sync(self.leave)(
        )
        return super().delete(
            using=using,
            keep_parents=keep_parents,
        )

    async def leave(self):
        responsible_user = await sync_to_async(getattr)(self, 'responsible_user')
        client: nio.AsyncClient = await responsible_user.aget_client()
        await client.room_leave(
            room_id=str(self.matrix_room_id),
        )

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


class MainUserKey(
    models.Model,
):
    service: ApplicationServiceRegistration = models.OneToOneField(
        ApplicationServiceRegistration,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    user: MatrixUser = models.OneToOneField(
        MatrixUser,
        on_delete=models.CASCADE,
    )
