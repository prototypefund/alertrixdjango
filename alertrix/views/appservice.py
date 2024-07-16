from django.urls import reverse
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


class DetailApplicationService(
    mixins.UserIsAdminForThisObjectMixin,
    mixins.ContextActionsMixin,
    DetailView,
):
    model = models.ApplicationServiceRegistration
    template_name = 'alertrix/applicationserviceregistration_detail.html'

    def get_context_actions(self):
        return [
            {'url': reverse('appservice.list'), 'label': _('back')},
            {'url': reverse('appservice.setup', kwargs=dict(pk=self.object.pk)), 'label': _('setup')},
        ]

    def get_context_data(self, **kwargs):
        cd = super().get_context_data(**kwargs)
        cd['namespaces'] = [
            [k, self.object.namespace_set.filter(scope=k)]
            for k in self.object.namespace_set.model.ScopeChoices
            if self.object.namespace_set.filter(scope=k)
        ]
        cd['check'] = self.check()
        return cd

    def check(self):
        return {
        }

    def get(self, request, *args, **kwargs):
        r = super().get(request, *args, **kwargs)
        self.check()
        return r


class SetupApplicationService(
    mixins.UserIsAdminForThisObjectMixin,
    mixins.ContextActionsMixin,
    DetailView,
):
    model = models.ApplicationServiceRegistration
    template_name = 'alertrix/applicationserviceregistration_setup.html'

    def get_context_actions(self):
        return [
            {'url': reverse('appservice.list'), 'label': _('list')},
            {'url': reverse('appservice.detail', kwargs=dict(pk=self.object.pk)), 'label': _('back')},
        ]

    def get_context_data(self, **kwargs):
        cd = super().get_context_data(**kwargs)
        cd['namespaces'] = [
            [k, self.object.namespace_set.filter(scope=k)]
            for k in self.object.namespace_set.model.ScopeChoices
            if self.object.namespace_set.filter(scope=k)
        ]
        return cd
