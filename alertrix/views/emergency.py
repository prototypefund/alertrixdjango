import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from matrixappservice import models as mas_models

from alertrix import models
from .. import mixins
from .. import querysets
from ..events import v1 as events
from ..forms.emergency import alert


class AlertView(
    FormView,
    LoginRequiredMixin,
    mixins.ContextActionsMixin,
):
    form_class = alert.AlertForm
    template_name = 'alertrix/form.html'
    context_actions = [
        {'name': 'comp.list', 'label': _('companies')},
    ]

    def get_success_url(self):
        return reverse('home')

    def get_initial(self):
        return {
            **super().get_initial(),
            'units': [
                self.request.GET.get('units'),
            ],
        }

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
        alert = events.Alert(
            **form.cleaned_data,
        )
        companies = querysets.get_companies_for_unit(
            form.cleaned_data.get('units'),
        )
        async for company in companies:
            bot = await mas_models.User.objects.aget(
                user_id=(await mas_models.Event.objects.aget(
                    type=events.AlertrixCompany().get_type(),
                    state_key='',
                    room=company,
                )).content['inbox'],
            )
            client = await bot.aget_client()
            units_this_bot_can_cover = models.Unit.objects.filter(
                # Room is requested by the unit field of the form
                Q(
                    room_id__in=form.cleaned_data['units'],
                ),
                # Bot is member of the room
                Q(
                    room_id__in=mas_models.Event.objects.filter(
                        type='m.room.member',
                        state_key=client.user_id,
                        content__membership='join',
                    ).values_list(
                        'room__room_id',
                        flat=True,
                    )
                ),
                # Room is registered as unit for the company
                Q(
                    room_id__in=mas_models.Event.objects.filter(
                        type=events.AlertrixCompanyUnit().get_type(),
                        room=company,
                    ).values_list(
                        'state_key',
                        flat=True,
                    )
                ),
            )
            # Filter for user_ids that the bot can write direct messages to
            members_of_all_relevant_units_the_bot_can_cover = mas_models.Event.objects.filter(
                type='m.room.member',
                room__room_id__in=units_this_bot_can_cover,
                content__membership='join',
            ).exclude(
                state_key=client.user_id,
            ).values_list(
                'state_key',
                flat=True,
            )
            async for recipient in members_of_all_relevant_units_the_bot_can_cover:
                dm = await querysets.aget_direct_message_for(
                    client.user_id,
                    recipient,
                )
                client.rooms[dm.room_id] = await dm.aget_nio_room(
                    own_user_id=client.user_id,
                )
                data = alert.get_matrix_data()
                room_send_response: nio.RoomSendResponse | nio.RoomSendError = await client.room_send(
                    dm.room_id,
                    data.pop('type'),
                    ignore_unverified_devices=True,
                    **data,
                )
            messages.info(
                self.request,
                _('sent alert to %(recipient_count)d recipients of %(company_name)s') % {
                    'recipient_count': await members_of_all_relevant_units_the_bot_can_cover.acount(),
                    'company_name': (await company.aget_name()).content['name'],  # TODO
                },
            )
            await client.close()
        return super().form_valid(form)
