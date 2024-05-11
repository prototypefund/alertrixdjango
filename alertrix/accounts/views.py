from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView

from matrixappservice.models import ApplicationServiceRegistration
from matrixappservice.models import Homeserver
from matrixappservice.models import User as MatrixUser
from . import forms
from . import models
from ..models import DirectMessage


class CreateUser(
    CreateView,
):
    model = get_user_model()
    form_class = forms.CreateUserForm
    template_name = 'alertrix/form.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        self.object = form.save()
        self.object.save()
        r = super().form_valid(form)
        group_name = settings.MATRIX_VALIDATED_GROUP_NAME
        try:
            group = Group.objects.get(
                name=group_name,
            )
        except Group.DoesNotExist:
            group = Group(
                name=group_name,
            )
            group.save()
        group.user_set.add(
            self.object,
        )
        group.save()
        messages.success(
            self.request,
            _('%(user)s has been added to %(group_name)s') % {
                'user': self.object,
                'group_name': group_name,
            },
        )
        messages.info(
            self.request,
            _('please make sure your password manager works by logging in'),
        )
        return r
