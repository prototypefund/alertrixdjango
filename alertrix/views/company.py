import logging

import django.forms.fields
import nio
import synapse.appservice
from asgiref.sync import async_to_sync
from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.detail import SingleObjectTemplateResponseMixin

from matrixappservice import models as mas_models
from . import matrixroom
from .. import forms
from .. import mixins
from .. import querysets
from ..events import v1 as events


class ListCompanies(
    LoginRequiredMixin,
    ListView,
):
    template_name = 'alertrix/company_list.html'

    def get_queryset(self):
        queryset = querysets.companies.filter(
            room_id__in=mas_models.Event.objects.filter(
                type='m.room.member',
                content__membership__in=['invite', 'join'],
                state_key=self.request.user.matrix_id,
            ).values_list('room_id', flat=True),
        )
        ordering = self.get_ordering()
        if ordering:
            if isinstance(ordering, str):
                ordering = (ordering,)
            queryset = queryset.order_by(*ordering)
        return queryset


class CreateCompany(
    PermissionRequiredMixin,
    mixins.ContextActionsMixin,
    matrixroom.CreateMatrixRoom,
    FormView,
):
    permission_required = 'alertrix.add_company'
    form_class = forms.company.CompanyCreateForm
    template_name = 'alertrix/form.html'
    http_method_names = [
        'get',
        'post',
    ]
    context_actions = [
        {'name': 'comp.list', 'label': _('list')},
    ]

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.fields['application_service'].choices = [
            (application_service.pk, application_service)
            for application_service in mas_models.ApplicationServiceRegistration.objects.filter(
                users__in=self.request.user.groups.all(),
            )
        ]
        return form

    def get_success_url(self):
        return reverse(
            'comp.detail',
            kwargs=dict(
                pk=self.instance.room_id,
            ),
        )

    def get_matrix_state_events(self, form):
        return [
            {
                'type': 'm.room.member',
                'content': {
                    'membership': 'join',
                    'displayname': form.data['name'],
                },
                'state_key': form.cleaned_data.get('responsible_user').user_id,
            },
            events.AlertrixCompany(
                inbox=form.cleaned_data.get('responsible_user').user_id,
            ).get_matrix_data(),
        ]

    def form_invalid(self, form):
        """
        Return a form response that has all the previous inputs in it (as per default), but also all the
        autogenerated content.
        """
        form.full_clean()
        initial = form.cleaned_data.copy()
        for name in form.fields:
            if name in form.cleaned_data:
                continue
            if hasattr(form, 'clean_%s' % name):
                initial[name] = getattr(form, 'clean_%s' % name)()
            else:
                initial[name] = form.data[name]
        new_form = self.get_form_class()(
            user=self.request.user,
            initial=initial,
        )
        new_form._errors = form._errors
        return self.render_to_response(self.get_context_data(form=new_form))

    def form_valid(self, form):
        mu: mas_models.User = form.cleaned_data['responsible_user']
        mu.save()
        self.responsible_user = form.cleaned_data.get('responsible_user')
        return super().form_valid(form=form)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        return data


class DetailCompany(
    mixins.UserHasSpecificMembershipForThisMatrixRoom,
    mixins.ContextActionsMixin,
    DetailView,
):
    model = mas_models.Room
    template_name = 'alertrix/company_detail.html'

    def get_context_actions(self):
        return [
            {'url': reverse('comp.list'), 'label': _('list')},
            {'url': reverse('comp.edit', kwargs=dict(pk=self.object.room_id)), 'label': _('edit')},
        ]

    def get_context_data(self, **kwargs):
        cd = super().get_context_data(**kwargs)
        cd['units'] = querysets.get_units_for_company(
            company=self.object,
        )
        return cd


class InviteUser(
    mixins.UserIsAdminForThisObjectMixin,
    mixins.ContextActionsMixin,
    SingleObjectTemplateResponseMixin,
    SingleObjectMixin,
    FormView,
):
    form_class = forms.company.InviteUser
    template_name = 'alertrix/form.html'

    def get_context_actions(self):
        return [
            {'url': reverse('comp.list'), 'label': _('list')},
            {'url': reverse('comp.detail', kwargs=dict(room_id=self.object.room_id)), 'label': _('back')},
        ]

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        room_id = self.object.room_id
        user_id = form.data['matrix_id']
        async_to_sync(self.invite_user)(
            user_id,
            room_id,
        )
        if form.data['power_level']:
            power_level = int(form.data['power_level'])
            async_to_sync(self.change_power_level)(
                user_id,
                room_id,
                power_level,
            )
        return super().form_valid(form)

    async def invite_user(
            self,
            user_id,
            room_id,
    ):
        mx_user = await sync_to_async(self.object.__getattribute__)('responsible_user')
        client = await mx_user.aget_client()
        resp = await client.room_invite(
            room_id,
            user_id,
        )
        if type(resp) == nio.RoomInviteResponse:
            messages.success(
                self.request,
                _('%(user_id)s has been invited') % {
                    'user_id': user_id,
                },
            )
        if type(resp) == nio.RoomInviteError:
            resp: nio.RoomInviteError
            messages.error(
                self.request,
                _('%(user_id)s could not be invited to this room: %(errcode)s %(error)s') % {
                    'user_id': user_id,
                    'error': resp.message,
                    'errcode': resp.status_code,
                },
            )
        return resp

    async def change_power_level(
            self,
            user_id,
            room_id,
            power_level,
    ):
        mx_user = await sync_to_async(self.object.__getattribute__)('responsible_user')
        client = await mx_user.aget_client()
        resp: nio.RoomGetStateResponse | nio.RoomGetStateError = await client.room_get_state(
            room_id,
        )
        if type(resp) == nio.RoomGetStateError:
            messages.error(
                self.request,
                _('unable to get room state: %(errcode)s %(error)s') % {
                    'errcode': resp.status_code,
                    'error': resp.message,
                },
            )
            return
        power_levels = None
        for event in resp.events:
            if event['type'] == 'm.room.power_levels':
                power_levels = event['content']
                break
        power_levels['users'][user_id] = power_level
        resp: nio.RoomPutStateError | nio.RoomPutStateResponse = await client.room_put_state(
            room_id,
            'm.room.power_levels',
            power_levels,
        )
        if type(resp) == nio.RoomPutStateResponse:
            messages.success(
                self.request,
                _('power level for %(user_id)s has been set to %(power_level)d') % {
                    'user_id': user_id,
                    'power_level': power_level,
                },
            )
        if type(resp) == nio.RoomPutStateError:
            messages.error(
                self.request,
                _('%(user_id)s\'s power level could not be set to %(power_level)d: %(errcode)s %(error)s') % {
                    'user_id': user_id,
                    'power_level': power_level,
                    'error': resp.message,
                    'errcode': resp.status_code,
                },
            )
        return resp

    def get_success_url(self):
        return reverse('comp.detail', kwargs={'slug': self.object.slug})

    def get_context_data(self, **kwargs):
        cd = super().get_context_data()
        cd['form'] = self.form_class()
        return cd


class UpdateCompany(
    mixins.ContextActionsMixin,
    FormView,
):
    form_class = forms.company.CompanyForm
    template_name = 'alertrix/form.html'

    def get_success_url(self):
        return reverse('comp.detail', kwargs={'slug': self.object.slug})

    def get_context_actions(self):
        return [
            {'url': reverse('comp.list'), 'label': _('list')},
            {'url': reverse('comp.detail', kwargs={'slug': self.object.slug}), 'label': _('back')},
        ]

    def form_valid(self, form):
        r = super().form_valid(form)
        async_to_sync(self.update_room_name)(form.cleaned_data['name'])
        async_to_sync(self.update_room_description)(form.cleaned_data['description'])
        return r

    async def put_room_state(
            self,
            event_type: str,
            content: dict,
    ):
        user = self.object.responsible_user
        client: nio.AsyncClient = await user.aget_client()
        response: nio.RoomPutStateResponse | nio.RoomPutStateError = await client.room_put_state(
            self.object.matrix_room_id,
            event_type,
            content,
        )
        if type(response) is nio.RoomPutStateError:
            messages.error(
                self.request,
                _('failed putting room state (%(event_type)s): %(errcode)s %(error)') % {
                    'event_type': event_type,
                    'errcode': response.status_code,
                    'error': response.message,
                },
            )

    async def update_room_name(self, name):
        return await self.put_room_state(
            'm.room.name',
            {
                'name': name,
            }
        )

    async def update_room_description(self, topic):
        return await self.put_room_state(
            'm.room.topic',
            {
                'topic': topic,
                'org.matrix.msc3765.topic': [
                    {
                        'body': topic,
                        'mimetype': 'text/plain',
                    },
                ],
            },
        )

    def get_form_kwargs(self):
        kwargs = {
            'user': self.request.user,
            **super().get_form_kwargs(),
        }
        kwargs['initial']['admin_group_name'] = self.object.admins.name
        kwargs['initial']['name'] = self.object.get_name()
        kwargs['initial']['description'] = self.object.get_description()
        return kwargs
