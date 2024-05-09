from django.contrib.auth.models import AbstractUser
from django.db import models
from matrixappservice.models import User as MatrixUser


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


class MatrixRoom(
    models.Model,
):
    matrix_room_id = models.TextField(
    )
    responsible_user = models.ForeignKey(
        MatrixUser,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
    )
