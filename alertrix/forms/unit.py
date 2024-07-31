from django import forms
from django.utils.translation import gettext_lazy as _

import matrixappservice.models
from . import matrixroom


class UnitForm(
    matrixroom.MatrixRoomForm,
):
    pass


class UnitCreateForm(
    matrixroom.MatrixRoomCreateForm,
    UnitForm,
):
    class Meta(
        matrixroom.MatrixRoomCreateForm.Meta,
        UnitForm.Meta,
    ):
        title = _('new unit')
        advanced = [
            *matrixroom.MatrixRoomCreateForm.Meta.advanced,
            *UnitForm.Meta.advanced,
            *[
                'responsible_user',
            ],
        ]
    companies = forms.MultipleChoiceField(
        label=_('companies'),
        widget=forms.CheckboxSelectMultiple,
    )
    responsible_user = forms.ChoiceField(
        label=_('responsible_user'),
        required=False,
    )

    def __init__(
            self,
            user,
            data=None,
            *args, **kwargs
    ):
        super().__init__(
            user=user,
            data=data,
            *args, **kwargs
        )
        if user.is_superuser:
            qs_companies = models.Company.objects.all()
        else:
            qs_companies = models.Company.objects.filter(
                admins__in=user.groups.all(),
            )
        self.fields['companies'].choices = [
            (c.slug, str(c))
            for c in qs_companies
        ]
        responsible_users = [
            (None, '---'),
        ] + [
            (responsible_user, str(matrixappservice.models.User.objects.get(user_id=responsible_user)))
            for responsible_user in qs_companies.values_list('responsible_user', flat=True)
        ]
        self.fields['responsible_user'].choices = (
            responsible_users
        )

    def clean_companies(self):
        if 'companies' not in self.data:
            self.add_error(
                'companies',
                _('you need to select at least one company'),
            )
            return
        return self.data.getlist('companies')

    def clean_responsible_user(self):
        companies = self.clean_companies()
        if not companies:
            self.add_error(
                'responsible_user',
                _('cannot select responsible user as not valid company is selected'),
            )
            return
        relevant_companies = models.Company.objects.filter(
            slug__in=[ident for ident, _ in self.fields['companies'].choices],
        ).filter(
            slug__in=self.clean_companies(),
        )
        if self.data['responsible_user']:
            if not relevant_companies.filter(
                    responsible_user__user_id=self.data['responsible_user'],
            ).exists():
                self.add_error(
                    'responsible_user',
                    _('this choice is not valid'),
                )
            return matrixappservice.models.User.objects.get(
                user_id=self.data['responsible_user'],
            )
        else:
            first_company = relevant_companies.first()
            return matrixappservice.models.User.objects.get(
                user_id=first_company.responsible_user,
            )
