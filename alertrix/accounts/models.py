import datetime

from django.conf import settings
from django.db import models
from . import utils


class RegistrationToken(
    models.Model,
):
    token = models.TextField(
        default=utils.get_token,
        primary_key=True,
    )
    valid_for_matrix_id = models.TextField(
    )
    requested_tms: datetime.datetime = models.DateTimeField(
        auto_now_add=True,
    )
    valid_for_duration: datetime.timedelta = models.DurationField(
        default=settings.ACCOUNTS_REGISTRATION_TOKEN_DURATION,
    )

    def is_valid(self):
        valid_until = self.requested_tms.timestamp() + self.valid_for_duration.total_seconds()
        return datetime.datetime.now().timestamp() < valid_until

    def __str__(self):
        return str(self.valid_for_matrix_id)
