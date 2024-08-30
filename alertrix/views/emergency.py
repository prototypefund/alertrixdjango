from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from matrixappservice import models as mas_models

from alertrix import models
from ..forms.emergency import alert


class AlertView(
    FormView,
):
    form_class = alert.AlertForm
    template_name = 'alertrix/form.html'

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
