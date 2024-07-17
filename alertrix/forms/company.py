import matrixappservice.exceptions
from django.core.exceptions import ValidationError
import synapse.appservice
from asgiref.sync import async_to_sync
from django import forms
from django.contrib.auth.models import Group
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from matrixappservice import models as mas_models
from . import matrixroom
from .. import models
from .. import widgets


class CompanyForm(
    matrixroom.MatrixRoomForm,
):
    class Meta(matrixroom.MatrixRoomForm.Meta):
        model = models.Company
        fields = [
            'name',
            'description',
            'matrix_room_id',
        ]


class CompanyCreateForm(
    CompanyForm,
):
    class Meta(CompanyForm.Meta):
        title = _('new company')
        fields = CompanyForm.Meta.fields + [
            'slug',
        ]
        optional = CompanyForm.Meta.optional + [
            'slug',
        ]
        advanced = CompanyForm.Meta.advanced + [
            'federate',
            'responsible_user',
            'slug',
            'admin_group_name',
        ]
    admin_group_name = forms.CharField(
        label=_('admin group name'),
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
        choices=[
            (application_service.pk, application_service)
            for application_service in models.ApplicationServiceRegistration.objects.all()
        ],
    )

    def clean_slug(self):
        slug = self.data.get('slug') or slugify(self.data.get('name'))
        if not slug:
            if 'slug' not in self.errors:
                self.add_error(
                    'slug',
                    _('%(field)s cannot be empty') % {
                        'field': self.fields['slug'].label,
                    },
                )
        return slug

    def clean_admin_group_name(self):
        admin_group_name = self.data.get('admin_group_name') or '%s_admins' % self.clean_slug()
        if not admin_group_name:
            if 'admin_group_name' not in self.errors:
                self.add_error(
                    'admin_group_name',
                    _('%(field)s cannot be empty') % {
                        'field': self.fields['admin_group_name'].label,
                    },
                )
        if self.user.groups.filter(
                name=admin_group_name,
        ).exists():
            return admin_group_name
        else:
            if Group.objects.filter(
                name=admin_group_name,
            ).exists():
                self.add_error(
                    'admin_group_name',
                    _('group already exists'),
                )
        return admin_group_name

    def clean_application_service(self):
        service = mas_models.ApplicationServiceRegistration.objects.get(
            pk=self.data.get('application_service'),
        )
        return service

    def clean_responsible_user(self):
        application_service = self.cleaned_data.get('application_service') or self.clean_application_service()
        if application_service is None:
            return
        user_namespaces = mas_models.Namespace.objects.filter(
            app_service=application_service,
            scope=mas_models.Namespace.ScopeChoices.users,
        )
        # Create a synapse instance to check if its application service is interested in the generated user id
        syn: synapse.appservice.ApplicationService = application_service.get_synapse_application_service()
        if not self.data['responsible_user']:
            # Prepare the user_id variable
            user_id = self.clean_slug()
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
        if mas_models.User.objects.filter(
                user_id=user_id,
        ).exists():
            mu = mas_models.User.objects.get(
                user_id=user_id,
            )
            devices = mas_models.Device.objects.filter(
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
            if models.Company.objects.filter(
                    responsible_user=mu,
            ).exists():
                comp = models.Company.objects.get(
                    responsible_user=mu,
                )
                if comp.responsible_user.user_id != user_id:
                    if 'responsible_user' not in self.errors:
                        self.add_error(
                            'responsible_user',
                            _('%(field)s already taken') % {
                                'field': self.fields['responsible_user'].label,
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
        mu = mas_models.User(
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
