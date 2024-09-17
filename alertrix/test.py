import abc

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from matrixappservice import models

from . import models as alertrix
from .views.company import CreateCompany
from .views.alert_channel import CreateAlertChannel


class AppserviceSetup(
    abc.ABC,
):
    def setUp(self):
        server_name = 'synapse.localhost'
        if not models.Homeserver.objects.filter(
                server_name=server_name,
        ):
            self.homeserver = models.Homeserver.objects.create(
                server_name=server_name,
            )
        else:
            self.homeserver = models.Homeserver.objects.get(
                server_name=server_name,
            )
        admins, new = Group.objects.get_or_create(
            name='admins',
        )
        if new:
            admins.save()
        self.validated_matrix_id_group, new = Group.objects.get_or_create(
            name=settings.MATRIX_VALIDATED_GROUP_NAME,
        )
        for model, view in (
                (alertrix.Company, CreateCompany),
                (alertrix.AlertChannel, CreateAlertChannel),
        ):
            content_type, new = ContentType.objects.get_or_create(
                app_label=model.__module__.split('.')[0],
                model=model.__name__,
            )
            permission, new = Permission.objects.get_or_create(
                codename=view.permission_required.split('.')[-1],
                content_type=content_type,
            )
            self.validated_matrix_id_group.permissions.add(
                permission,
            )
        self.app_service, new = models.ApplicationServiceRegistration.objects.get_or_create(
            homeserver=self.homeserver,
            id_homeserver='alertrix',
            as_token='<as_token>',
            hs_token='<hs_token>',
            admins=admins,
            users=self.validated_matrix_id_group,
            rate_limited=False,
        )
        if new:
            self.app_service.save()
        models.Namespace.objects.get_or_create(
            app_service=self.app_service,
            scope=models.Namespace.ScopeChoices.users,
            exclusive=True,
            regex='@alertrix_*',
        )
        main_as_key, new = alertrix.MainApplicationServiceKey.objects.get_or_create(
            service=self.app_service,
        )
        main_as_user, new = models.User.objects.get_or_create(
            user_id='@alertrix_test_main:synapse.localhost',
            app_service=main_as_key.service,
        )
        main_as_user_key, new = alertrix.MainUserKey.objects.get_or_create(
            service=main_as_key.service,
            user=main_as_user,
        )
