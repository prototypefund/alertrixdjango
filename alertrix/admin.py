from django.contrib import admin

from . import models

admin.site.register(
    models.Handler,
)

admin.site.register(
    models.MainApplicationServiceKey,
)
