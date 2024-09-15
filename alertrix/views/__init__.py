import json
import secrets
import string

import matrixappservice
import nio
from asgiref.sync import async_to_sync
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import loader
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from matrixappservice import models as mas_models
from matrixappservice.database import models as database

from . import alert_channel
from . import appservice
from . import company
from . import emergency
from . import unit
from .. import forms
from .. import models
from .. import querysets


def home(request):
    main_user = None
    try:
        main_user = models.MainApplicationServiceKey.objects.get(id=1).service.mainuserkey.user
    except models.MainApplicationServiceKey.DoesNotExist:
        messages.error(
            request,
            _('no main application service has been set'),
        )
    except matrixappservice.models.ApplicationServiceRegistration.mainuserkey.RelatedObjectDoesNotExist:
        messages.error(
            request,
            _('no main user set for the main application service'),
        )
    return render(
        request,
        'alertrix/home.html',
        context={
            'main_user': main_user,
            'units': models.Unit.objects.filter(
                room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_units': querysets.units.count(),
            'companies': querysets.companies.filter(
                room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership__in=['invite', 'join'],
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_companies': querysets.companies.count(),
        },
    )


class WidgetActivationView(
    FormView,
):
    model = models.Widget
    form_class = forms.WidgetLoginForm
    template_name = 'alertrix/form.html'
    success_url = '/'

    def get_object(self):
        self.object = get_object_or_404(
            self.model,
            id=self.request.GET['widgetId'],
        )
        return self.object

    def form_valid(self, form):
        login(
            self.request,
            get_user_model().objects.get(
                matrix_id=self.object.user_id,
            ),
        )
        self.object.first_use_timestamp = timezone.now()
        self.object.save()
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        self.request = request
        self.get_object()
        # Generate a new secret
        self.object.activation_secret = ''.join([
            secrets.choice(string.digits)
            for _ in range(models.Widget.activation_secret.field.max_length)
        ])
        self.object.save()
        # … and send it to the user in an encrypted message
        users = mas_models.User.objects.filter(
            Q(
                user_id__in=self.object.room.get_joined_members().values_list(
                    'state_key',
                    flat=True,
                ),
            ),
            Q(
                user_id__in=database.Account.objects.filter(
                    account__isnull=False,
                ).values_list(
                    'user_id',
                    flat=True,
                ),
            ),
            prevent_automated_responses=False,
        )
        user = users.first()
        client = user.get_client()
        if self.object.room.room_id not in client.rooms:
            client.rooms[self.object.room.room_id] = self.object.room.get_nio_room(
                client.user_id,
            )
        room_send_response = async_to_sync(client.room_send)(
            room_id=self.object.room.room_id,
            message_type='m.room.message',
            content=json.loads(loader.render_to_string(
                'alertrix/cli/widget_activation_secret.json',
                {
                    'widget': self.object,
                },
            )),
        )
        if type(room_send_response) is nio.RoomSendError:
            messages.error(
                request,
                str(room_send_response),
            )
        else:
            messages.info(
                request,
                _('the activation secret for this widget has been sent to %(user_id)s') % {
                    'user_id': self.object.user_id,
                },
            )
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.object
        # Hide the activation_secret from the form. Showing this here would defy the purpose of this view.
        kwargs['initial']['activation_secret'] = None
        kwargs['initial']['id'] = self.request.GET.get('widgetId')
        return kwargs

    def post(self, request, *args, **kwargs):
        self.request = request
        self.get_object()
        return super().post(request, *args, **kwargs)
