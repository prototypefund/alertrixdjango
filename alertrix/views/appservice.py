from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from django.views.generic import DetailView
from .. import mixins
from .. import models


class ListApplicationServices(
    ListView,
):
    model = models.ApplicationServiceRegistration
    template_name = 'alertrix/applicationserviceregistration_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.has_perm('matrixappservice.view_applicationserviceregistration'):
            return queryset
        qs = queryset.filter(
            admins__in=self.request.user.groups.all(),
        )
        return qs
