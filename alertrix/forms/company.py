from django.core.exceptions import ValidationError
import synapse.appservice
from asgiref.sync import async_to_sync
from django import forms
from django.contrib.auth.models import Group
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from matrixappservice import models as mas_models
from .. import models
from .. import widgets


class CompanyForm(
    forms.ModelForm,
):
    class Meta:
        title = _('new company')
        model = models.Company
        fields = [
            'name',
            'description',
            'handler',
            'slug',
            'matrix_room_id',
        ]
        widgets = {
            'matrix_room_id': forms.Textarea(
                attrs={
                    'rows': 1,
                    'style': ';'.join([
                        'resize: none',
                    ]),
                },
            ),
        }
        optional = [
            'slug',
            'matrix_room_id',
        ]
        advanced = [
            'slug',
            'matrix_room_id',
            'federate',
            'matrix_user_id',
            'admin_group_name',
        ]
    name = forms.CharField(
        label=_('name'),
        widget=forms.Textarea(
            attrs={
                'rows': 1,
                'style': ';'.join([
                    'resize: none',
                ]),
            },
        ),
    )
    description = forms.CharField(
        label=_('description'),
        widget=forms.Textarea(
            attrs={
            },
        ),
        required=False,
    )
    matrix_user_id = forms.CharField(
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

    def __init__(
            self,
            user,
            data=None,
            *args, **kwargs
    ):
        super().__init__(
            data=data,
            *args, **kwargs
        )
        self.user = user
        for field_name in self.Meta.optional:
            self.fields[field_name].required = False
        for field_name in self.Meta.advanced:
            self.fields[field_name].widget.attrs['class'] = 'advanced'

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

    def clean_handler(self):
        raw_selection = self.data['handler']
        if not raw_selection:
            if 'handler' not in self.errors:
                self.add_error(
                    'handler',
                    _('handler cannot be empty'),
                )
            return
        try:
            handler_id = models.Handler._meta.get_field('id').to_python(raw_selection)
        except ValidationError:
            if 'handler' not in self.errors:
                self.add_error(
                    'handler',
                    _('invalid handler id'),
                )
            return
        handler = models.Handler.objects.get(
            id=handler_id,
        )
        if self.user.groups.filter(id=handler.users.id).count() < 1:
            if 'handler' not in self.errors:
                self.add_error(
                    'handler',
                    _('you are not allowed to use this %(object)s') % {
                        'object': models.Handler.Meta.verbose_name,
                    },
                )
            return
        return handler

    def clean_matrix_user_id(self):
        handler = self.clean_handler()
        if handler is None:
            return
        user_namespaces = mas_models.Namespace.objects.filter(
            app_service=handler.application_service,
            scope=mas_models.Namespace.ScopeChoices.users,
        )
        # Create a synapse instance to check if its application service is interested in the generated user id
        syn: synapse.appservice.ApplicationService = async_to_sync(
            handler.application_service.get_synapse_application_service
        )()
        if not self.data['matrix_user_id']:
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
                        'server_name': handler.application_service.homeserver.server_name,
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
                        'matrix_user_id',
                        _('%(field)s could not be corrected automatically') % {
                            'field': self.fields['matrix_user_id'].label,
                        },
                        )
        else:
            user_id = self.data['matrix_user_id']
        if not syn.is_interested_in_user(
            user_id=user_id,
        ):
            if 'matrix_user_id' not in self.errors:
                self.add_error(
                    'matrix_user_id',
                    _('%(app_service)s is not interested in %(user_id)s') % {
                        'app_service': handler.application_service,
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
                if 'matrix_user_id' not in self.errors:
                    self.add_error(
                        'matrix_user_id',
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
                    if 'matrix_user_id' not in self.errors:
                        self.add_error(
                            'matrix_user_id',
                            _('%(field)s already taken') % {
                                'field': self.fields['matrix_user_id'].label,
                            },
                        )
        else:
            account_info = async_to_sync(handler.application_service.request)(
                method='GET',
                path='/_matrix/client/v3/profile/%(user_id)s' % {
                    'user_id': user_id,
                },
            )
            if 'errcode' not in account_info:
                self.add_error(
                    'matrix_user_id',
                    _('%(user_id)s already exists on the homeserver but is unknown to the application service') % {
                        'user_id': user_id,
                    },
                )
        return user_id


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
