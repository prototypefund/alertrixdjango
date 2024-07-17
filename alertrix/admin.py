from django.contrib import admin

from . import models


class CompanyAdmin(admin.ModelAdmin):
    readonly_fields = [
        'slug',
    ]


admin.site.register(
    models.MainApplicationServiceKey,
)

admin.site.register(
    models.DirectMessage,
)

admin.site.register(
    models.Company,
    CompanyAdmin,
)

admin.site.register(
    models.Unit,
)

admin.site.register(
    models.MainUserKey,
)
