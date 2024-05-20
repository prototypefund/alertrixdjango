from django.contrib import admin
from django.contrib.auth import forms as auth
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from alertrix.models import User
from . import models


admin.site.register(
    models.RegistrationToken,
)
