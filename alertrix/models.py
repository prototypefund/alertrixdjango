from django.contrib.auth.models import AbstractUser
from django.db import models
from matrixappservice.models import User as MatrixUser


class User(
    AbstractUser,
):
    USERNAME_FIELD = 'matrix_id'
    username = models.TextField(
        primary_key=True,
    )
    matrix_id = models.TextField(
        unique=True,
        blank=True,
    )

    def __str__(self):
        return str(self.username)


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
