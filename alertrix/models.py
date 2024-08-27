import logging
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
