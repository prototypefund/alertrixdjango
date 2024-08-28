import matrixappservice.exceptions
import synapse.appservice
from asgiref.sync import async_to_sync
from django import forms
from django.contrib.auth.models import Group
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from matrixappservice import models
from . import matrixroom
from .. import widgets


class CompanyForm(
    matrixroom.MatrixRoomForm,
):
    class Meta(matrixroom.MatrixRoomForm.Meta):
        fields = [
            'name',
            'description',
            'room_id',
        ]


class CompanyCreateForm(
    CompanyForm,
):
    class Meta(CompanyForm.Meta):
        title = _('new company')
        fields = CompanyForm.Meta.fields + [
        ]
        optional = CompanyForm.Meta.optional + [
        ]
        advanced = CompanyForm.Meta.advanced + [
            'federate',
            'responsible_user',
        ]
    federate = forms.BooleanField(
        label=_('federate'),
        initial=True,
        required=False,
    )
    responsible_user = forms.CharField(
        label=_('matrix user id'),
        widget=forms.Textarea(
            attrs={
                'rows': 1,
                'style': ';'.join([
                    'resize: none',
                ]),
            },
        ),
        required=False,
    )
    application_service = forms.ChoiceField(
        choices=models.ApplicationServiceRegistration.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['application_service'].choices = [
            (application_service.pk, application_service)
            for application_service in models.ApplicationServiceRegistration.objects.all()
        ]

    def clean_application_service(self):
        service = models.ApplicationServiceRegistration.objects.get(
            pk=self.data.get('application_service'),
        )
        return service

    def clean_responsible_user(self):
        application_service = self.cleaned_data.get('application_service') or self.clean_application_service()
        if application_service is None:
            return
        user_namespaces = models.Namespace.objects.filter(
            app_service=application_service,
            scope=models.Namespace.ScopeChoices.users,
        )
        # Create a synapse instance to check if its application service is interested in the generated user id
        syn: synapse.appservice.ApplicationService = application_service.get_synapse_application_service()
        if 'responsible_user' not in self.data or self.data.get('responsible_user') is None:
            # Prepare the user_id variable
            user_id = slugify(self.data['name'])
            if not syn.is_interested_in_user(
                    user_id=user_id,
            ):
                for namespace in user_namespaces:
                    if '*' not in namespace.regex:
                        continue
                    localpart = namespace.regex.lstrip('@').replace(
                        '*',
                        user_id,
                    )
                    interested_check_against = '@%(localpart)s:%(server_name)s' % {
                        'localpart': localpart,
                        'server_name': application_service.homeserver.server_name,
                    }
                    if not syn.is_interested_in_user(
                            user_id=interested_check_against,
                    ):
                        continue
                    # Overwrite user_id variable
                    user_id = interested_check_against
                    break
                if not user_id:
                    self.add_error(
                        'responsible_user',
                        _('%(field)s could not be corrected automatically') % {
                            'field': self.fields['responsible_user'].label,
                        },
                        )
        else:
            user_id = self.data['responsible_user']
        if not syn.is_interested_in_user(
            user_id=user_id,
        ):
            if 'responsible_user' not in self.errors:
                self.add_error(
                    'responsible_user',
                    _('%(app_service)s is not interested in %(user_id)s') % {
                        'app_service': application_service,
                        'user_id': user_id,
                    },
                )
        if models.User.objects.filter(
                user_id=user_id,
        ).exists():
            mu = models.User.objects.get(
                user_id=user_id,
            )
            devices = models.Device.objects.filter(
                user=mu,
            )
            if devices.count() < 1:
                if 'responsible_user' not in self.errors:
                    self.add_error(
                        'responsible_user',
                        _('%(user_id)s is misconfigured and cannot be used') % {
                            'user_id': user_id,
                        },
                    )
            return mu
        else:
            account_info = async_to_sync(application_service.request)(
                method='GET',
                path='/_matrix/client/v3/profile/%(user_id)s' % {
                    'user_id': user_id,
                },
            )
            if 'errcode' not in account_info:
                self.add_error(
                    'responsible_user',
                    _('%(user_id)s already exists on the homeserver but is unknown to the application service') % {
                        'user_id': user_id,
                    },
                )
        mu = models.User(
            user_id=user_id,
            homeserver=application_service.homeserver,
            app_service=application_service,
        )
        try:
            mu.save()
            return mu
        except matrixappservice.exceptions.MUserInUse:
            self.add_error(
                'responsible_user',
                _('%(user_id)s already exists on the homeserver') % {
                    'user_id': user_id,
                },
            )


class InviteUser(
    forms.Form,
):
    matrix_id = forms.CharField(
    )
    power_level = forms.IntegerField(
        max_value=100,
        min_value=0,
        required=False,
        widget=widgets.IntegerWithRecommendationsField(
            options=[
                {'value': 0, 'label': _('standard')},
                {'value': 50, 'label': _('moderator')},
                {'value': 100, 'label': _('admin')},
            ],
        ),
    )

    class Meta:
        title = _('invite user')
        submit_text = _('invite')
        fields = (
            'matrix_id',
            'power_level',
        )
