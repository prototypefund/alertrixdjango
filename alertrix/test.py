import abc

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from matrixappservice import models

from . import models as alertrix
from .views.company import CreateCompany


class AppserviceSetup(
    abc.ABC,
):
    def setUp(self):
        self.homeserver, new = models.Homeserver.objects.get_or_create(
            server_name='synapse.localhost',
            url='http://matrix.synapse.localhost',
        )
        if new:
            self.homeserver.save()
        admins, new = Group.objects.get_or_create(
            name='admins',
        )
        if new:
            admins.save()
        self.validated_matrix_id_group, new = Group.objects.get_or_create(
            name=settings.MATRIX_VALIDATED_GROUP_NAME,
        )
        if new:
            content_type, new = ContentType.objects.get_or_create(
                app_label=alertrix.Company.__module__.split('.')[0],
                model=alertrix.Company.__name__,
            )
            permission, new = Permission.objects.get_or_create(
                codename=CreateCompany.permission_required.split('.')[-1],
                content_type=content_type
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
