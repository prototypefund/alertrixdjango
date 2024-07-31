from django.contrib import admin

from . import models


admin.site.register(
    models.MainApplicationServiceKey,
)

admin.site.register(
    models.DirectMessage,
)

admin.site.register(
    models.Unit,
)

admin.site.register(
    models.MainUserKey,
)
