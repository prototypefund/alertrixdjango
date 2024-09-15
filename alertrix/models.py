import logging
from typing import List
import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from matrixappservice import exceptions as exc
from matrixappservice.models import ApplicationServiceRegistration
from matrixappservice.models import User as MatrixUser
from matrixappservice.models import Event
from matrixappservice.models import Room
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


class DirectMessageManager(
    models.Manager,
):

    def get_queryset(self):
        return Room.objects.filter(
            room_id__in=Event.objects.filter(
                Q(
                    content__membership='invite',
                    content__is_direct=True,
                ) | Q(
                    content__membership='join',
                    unsigned__prev_content__is_direct=True,
                ),
                ).values_list(
                'room__room_id',
                flat=True,
            ),
        )

    def get_for(
            self,
            *users: str,
            valid_memberships: List[str] = None,
    ) -> Room:
        if valid_memberships is None:
            valid_memberships = [
                'join',
            ]
        queryset = self.get_queryset()
        for user in users:
            queryset = queryset.intersection(
                self.filter(
                    room_id__in=Event.objects.filter(
                        content__membership__in=valid_memberships,
                        state_key=user,
                    ).values_list(
                        'room__room_id',
                        flat=True,
                    ),
                )
            )
        try:
            return queryset.get()
        except Room.MultipleObjectsReturned as e:
            logging.error(
                'returned too many rooms: %(room_list)s' % {
                    'room_list': str(queryset),
                },
            )
            raise e

    async def aget_for(
            self,
            *users: str,
            valid_memberships: List[str] = None,
    ) -> Room:
        return await sync_to_async(self.get_for)(
            *users,
            valid_memberships=valid_memberships,
        )


class DirectMessage(
    Room,
):
    objects = DirectMessageManager()

    class Meta:
        proxy = True


class CompanyManager(
    models.Manager,
):

    def get_queryset(self):
        return Room.objects.filter(
            room_id__in=Event.objects.filter(
                type='%(prefix)s.company' % {
                    'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
                },
                state_key__isnull=False,
            ).values_list(
                'room__room_id',
                flat=True,
            ),
        )


class Company(
    Room,
):
    objects = CompanyManager()

    class Meta:
        proxy = True


class UnitManager(
    models.Manager,
):

    def get_queryset(self):
        return Room.objects.filter(
            room_id__in=Event.objects.filter(
                type='%(prefix)s.company.unit' % {
                    'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
                },
                content__isnull=False,
                state_key__isnull=False,
                room__in=Company.objects.all(),
            ).values_list(
                'state_key',
                flat=True,
            ),
        )


class Unit(
    Room,
):
    objects = UnitManager()

    class Meta:
        proxy = True


class Widget(
    models.Model,
):
    id = models.TextField(
        primary_key=True,
    )
    room = models.ForeignKey(
        Room,
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
    activation_secret = models.CharField(
        max_length=4,
        verbose_name=_('activation secret'),
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
