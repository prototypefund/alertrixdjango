import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from matrixappservice import models as mas_models

from alertrix import models
from .. import mixins
from ..forms.emergency import alert


class AlertView(
    FormView,
    mixins.ContextActionsMixin,
):
    form_class = alert.AlertForm
    template_name = 'alertrix/form.html'
    context_actions = [
        {'name': 'comp.list', 'label': _('companies')},
    ]

    def get_success_url(self):
        return reverse('home')

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields['units'].choices = [
            (unit.pk, unit.get_name().content['name'])
            for unit in models.Unit.objects.filter(
                room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=self.request.user.matrix_id,
                ).values_list(
                    'room__room_id',
                    flat=True,
                ),
            )
        ]
        return form

    def form_valid(self, form):
        return async_to_sync(self.aform_valid)(form)

    async def aform_valid(self, form):
        return super().form_valid(form)
