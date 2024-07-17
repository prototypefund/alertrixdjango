import nio
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DetailView

from . import matrixroom
from .. import forms
from .. import models


class CreateUnit(
    matrixroom.CreateMatrixRoom,
    CreateView,
):
    model = models.Unit
    form_class = forms.unit.UnitCreateForm
    template_name = 'alertrix/form.html'
    success_url = reverse_lazy('comp.list')

    def get_initial(self):
        preselected_companies = models.Company.objects.filter(
            slug__in=self.request.GET.getlist('companies'),
        )
        initial = {
            **super().get_initial(),
            **{
                'companies': [c for c in preselected_companies.values_list('pk', flat=True)],
            },
        }
        return initial

    def get_matrix_state_events(self, form):
        state_events = []
        for c in form.cleaned_data['companies']:
            company = models.Company.objects.get(slug=c)
            via = models.Company.objects.filter(
                slug__in=form.cleaned_data['companies']
            ).values_list(
                'responsible_user__homeserver__server_name',
                flat=True,
            )
            state_events.append({
                'room_id': company.matrix_room_id,
                'type': 'm.space.child',
                'content': {
                    'via': list(via),
                },
                'state_key': self.object.matrix_room_id,
            })
        return state_events

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
                            'room_id': models.Company.objects.get(slug=company).matrix_room_id,
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
    mixins.LoginRequiredMixin,
    mixins.UserPassesTestMixin,
    DetailView,
):
    model = models.Unit

    async def aget_joined_members(self):
        self.object = await sync_to_async(self.get_object)()
        responsible_user = await sync_to_async(getattr)(self.object, 'responsible_user')
        client: nio.AsyncClient = await responsible_user.aget_client()
        joined_members_response: nio.JoinedMembersResponse | nio.JoinedMembersError = await client.joined_members(
            self.object.matrix_room_id,
        )
        return joined_members_response

    def test_func(self):
        joined_members_response = async_to_sync(self.aget_joined_members)()
        if self.request.user.matrix_id in [
            user.user_id
            for user in joined_members_response.members
        ]:
            return True
        return False
