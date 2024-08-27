import abc

from django.conf import settings
from django.contrib.auth.models import Group
from matrixappservice import models


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
        self.app_service, new = models.ApplicationServiceRegistration.objects.get_or_create(
            homeserver=self.homeserver,
            id_homeserver='alertrix',
            as_token='<as_token>',
            hs_token='<hs_token>',
            admins=admins,
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
