import nio
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from django.views.generic import CreateView

from matrixappservice.models import ApplicationServiceRegistration
from matrixappservice.models import Homeserver
from matrixappservice.models import User as MatrixUser
from matrixappservice.models import Room
from . import forms
from . import models
from . import utils
from ..models import MainApplicationServiceKey
from ..models import MainUserKey
from ..querysets import get_direct_message_for


class CreateRegistrationToken(
    CreateView,
):
    form_class = forms.CreateRegistration
    model = models.RegistrationToken
    template_name = 'alertrix/form.html'
    registration_user_selected_cookie_name = 'registration_user_id'

    def get_success_url(self):
        return reverse_lazy('validate', kwargs={'matrix_id': self.object.valid_for_matrix_id})

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        # Make sure, all the required dependencies are set up
        try:
            main_service = MainApplicationServiceKey.objects.get(id=1).service
            user_id = '@%(localpart)s:%(server_name)s' % {
                'localpart': main_service.sender_localpart,
                'server_name': main_service.homeserver.server_name,
            }
            responsible_user = MatrixUser.objects.get(
                app_service=main_service,
                user_id=user_id,
            )
            DirectMessage.objects.get(
                responsible_user=responsible_user,
                with_user=form.data.get('valid_for_matrix_id'),
            )
        except MainApplicationServiceKey.DoesNotExist:
            messages.error(
                self.request,
                _('no main application service registration has been specified yet'),
            )
            return self.form_invalid(form)
        except MatrixUser.DoesNotExist:
            messages.error(
                self.request,
                _('this service is not set up to send messages'),
            )
            return self.form_invalid(form)
        except DirectMessage.DoesNotExist:
            messages.error(
                self.request,
                _('invite <a href="https://matrix.to/#/%(user_id)s">%(user_id)s</a> to a direct message first') % {
                    'user_id': responsible_user.user_id,
                },
                extra_tags='safe',
            )
            return self.form_invalid(form)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        r = super().form_valid(form)
        app_service = MainApplicationServiceKey.objects.get(id=1).service
        try:
            success = async_to_sync(self.send_token)(
                app_service=app_service,
                user_id=form.data['valid_for_matrix_id'],
                token=self.object.token,
            )
        except DirectMessage.DoesNotExist:
            success = False
        if success:
            self.request.session[self.registration_user_selected_cookie_name] = form.data['valid_for_matrix_id']
            self.request.session.set_expiry(settings.ACCOUNTS_REGISTRATION_TOKEN_DURATION)
        return r

    async def send_token(
            self,
            app_service: ApplicationServiceRegistration,
            user_id: str,
            token: str,
    ):
        try:
            # Save the direct message object
            dm = await DirectMessage.objects.aget(
                with_user=user_id,
                responsible_user=await app_service.get_user(),
            )
        except DirectMessage.DoesNotExist:
            # There could be a room creation process here, but that could be used to spam users using the primary
            # application services account.
            return
        client: nio.AsyncClient = await app_service.get_matrix_client()
        # send the token
        room_send_response: nio.RoomSendResponse | nio.RoomSendError = await client.room_send(
            dm.matrix_room_id,
            'm.room.message',
            {
                'body': _('use this token to register on %(url)s: %(token)s') % {
                    'url': self.request.get_host(),
                    'token': token
                },
                'msgtype': 'm.text',
                'format': 'org.matrix.custom.html',
                'formatted_body': _(
                    '<p>use this token to register on <a href="%(url)s">%(host)s</a></p>'
                    '\n<pre><code>%(token)s</code></pre>',
                ) % {
                    'url': ''.join([
                        'http',
                        's' if self.request.is_secure() else '',
                        '://',
                        self.request.get_host(),
                        ':' + self.request.get_port() if self.request.get_port else '',
                    ]),
                    'host': self.request.get_host(),
                    'token': token,
                },
            },
        )
        if type(room_send_response) is nio.RoomSendResponse:
            return True
        if type(room_send_response) is nio.RoomSendError:
            messages.error(
                self.request,
                _('failed to send token to %(user_id)s: %(errcode)s %(error)s') % {
                    'user_id': user_id,
                    'errcode': room_send_response.status_code,
                    'error': room_send_response.message,
                },
            )


class CreateFirstUser(
    CreateView,
):
    model = get_user_model()
    form_class = forms.CreateFirstUserForm
    template_name = 'alertrix/form.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        resp = super().form_valid(form)
        self.object.is_staff = True
        self.object.is_superuser = True
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
        group.user_set.add(self.object)
        group.save()
        self.object.save()
        server_name = self.object.matrix_id.split(':')[1]
        server_info = async_to_sync(utils.get_server_well_known)(server_name)
        hs = Homeserver(
            server_name=server_name,
            url=server_info['m.homeserver']['base_url'],
        )
        hs.save()
        messages.success(
            self.request,
            _('based on you user name, the homeserver on %(url)s has been added') % {
                'url': hs.url,
            },
        )
        return resp


class CreateUser(
    UpdateView,
):
    model = get_user_model()
    form_class = forms.CreateUserForm
    template_name = 'alertrix/form.html'
    success_url = reverse_lazy('login')
    pk_url_kwarg = 'matrix_id'

    def get_initial(self):
        initial = super().get_initial()
        if CreateRegistrationToken.registration_user_selected_cookie_name in self.request.session:
            initial['matrix_id'] = self.request.session[CreateRegistrationToken.registration_user_selected_cookie_name]
        return initial

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


def registration_or_first_user_view(request):
    if get_user_model().objects.count() == 0:
        return CreateFirstUser.as_view()(request)
    return CreateRegistrationToken.as_view()(request)
