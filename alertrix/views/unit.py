from typing import Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from matrixappservice import models
from matrixappservice.database import models as database

from . import matrixroom
from .. import forms
from .. import mixins
from .. import querysets


class CreateUnit(
    LoginRequiredMixin,
    matrixroom.CreateMatrixRoom,
    FormView,
):
    form_class = forms.unit.UnitCreateForm
    template_name = 'alertrix/form.html'
    success_url = reverse_lazy('comp.list')

    def get_initial(self):
        preselected_companies = querysets.companies.filter(
            Q(
                room_id__in=self.request.GET.getlist('companies')
            ) & Q(
                room_id__in=models.Event.objects.filter(
                    type='m.room.member',
                    content__membership__in=['invite', 'join'],
                ).values_list(
                    'room__room_id',
                    flat=True,
                ),
            ),
        )
        initial = {
            **super().get_initial(),
            **{
                'companies': [c for c in preselected_companies.values_list('pk', flat=True)],
            },
        }
        return initial

    def get_relevant_users(self, form):
        relevant_users = models.User.objects.filter(
            Q(  # check if usable account data is present
                user_id__in=database.Account.objects.filter(
                    account__isnull=False,
                ).values_list(
                    'user_id',
                    flat=True,
                ),
            ),
            Q(  # filter for users that are registered as inbox for one of the selected companies
                user_id__in=models.Event.objects.filter(
                    Q(
                        room__room_id__in=form.cleaned_data.get('companies'),
                    ),
                    Q(
                        room__in=querysets.companies,
                    ),
                    type='%(prefix)s.company' % {
                        'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
                    },
                    content__inbox__isnull=False,
                    state_key='',
                ).values_list(
                    'content__inbox',
                    flat=True,
                ),
            ),
        )
        return relevant_users

    def get_invites(self, form):
        invites = self.get_relevant_users(
            form,
        )
        return invites

    def get_events_permission_level(self) -> Optional[dict[str, int]]:
        return {
            '%(prefix)s.company' % {
                'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
            }: 100,
            '%(prefix)s.company.unit' % {
                'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
            }: 100,
        }

    async def aget_secondary_matrix_state_events(self, form, room_id):
        for c in form.cleaned_data['companies']:
            company = await models.Room.objects.aget(room_id=c)
            via = models.Event.objects.filter(
                room__room_id=c,
                type='m.room.member',
                content__membership='join',
            ).values_list(
                'sender__homeserver__server_name',
                flat=True,
            )
            yield {
                'room_id': company.room_id,
                'type': 'm.space.child',
                'content': {
                    'via': await sync_to_async(list)(via),
                },
                'state_key': room_id,
            }
            yield {
                'room_id': company.room_id,
                'type': '%(prefix)s.company.unit' % {
                    'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
                },
                'content': {
                    'version': '0',
                },
                'state_key': room_id,
            }

    def get_matrix_room_args(
            self,
            form,
            **kwargs
    ):
        args = super().get_matrix_room_args(
            form=form,
            **kwargs,
        )
        args['initial_state'] = args['initial_state'] + [
            {
                'type': 'm.room.join_rules',
                'content': {
                    'join_rule': 'restricted',
                    'allow': [
                        {
                            'type': 'm.room_membership',
                            'room_id': company,
                        }
                        for company in form.cleaned_data['companies']
                    ]
                },
            },
        ]
        for c in form.cleaned_data['companies']:
            company = models.Company.objects.get(slug=c)
            via = models.Company.objects.filter(
                slug__in=form.cleaned_data['companies']
            ).values_list(
                'responsible_user__homeserver__server_name',
                flat=True,
            )
            args['initial_state'].append({
                'type': 'm.space.parent',
                'state_key': company.matrix_room_id,
                'content': {
                    'via': list(via),
                }
            })
        return args


class UnitDetailView(
    mixins.UserHasSpecificMembershipForThisMatrixRoom,
    DetailView,
):
    model = models.Room
