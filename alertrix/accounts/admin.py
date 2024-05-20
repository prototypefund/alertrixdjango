from django.contrib import admin
from django.contrib.auth import forms as auth

from . import models


admin.site.register(
    models.RegistrationToken,
)
