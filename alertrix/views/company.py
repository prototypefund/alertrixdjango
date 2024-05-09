from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from .. import forms
from .. import models


class CreateCompany(
    PermissionRequiredMixin,
    CreateView,
):
    permission_required = 'alertrix.add_company'
    model = models.Company
    form_class = forms.company.CompanyForm
    template_name = 'alertrix/form.html'
    http_method_names = [
        'get',
        'post',
    ]

    def get_form_kwargs(self):
        kwargs = {
            'user': self.request.user,
            **super().get_form_kwargs(),
        }
        return kwargs

    def get_success_url(self):
        return reverse('comp.detail', kwargs={'slug': self.object.slug})
