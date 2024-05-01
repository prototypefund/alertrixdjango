from django.contrib.auth.models import AbstractUser
from django.db import models


class User(
    AbstractUser,
):
    username = models.TextField(
        primary_key=True,
    )
    matrix_id = models.TextField(
        unique=True,
        blank=True,
    )

    def __str__(self):
        return str(self.username)
