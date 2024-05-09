from django import forms
from django.utils.text import slugify
from .. import models


class CompanyForm(
    forms.ModelForm,
):
    class Meta:
        model = models.Company
        fields = [
            'name',
            'handler',
            'slug',
            'admins',
            'matrix_room_id',
        ]
        widgets = {
        }
        optional = [
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

    def __init__(
            self,
            data=None,
            *args, **kwargs
    ):
        super().__init__(
            data=data,
            *args, **kwargs
        )
        for field_name in self.Meta.optional:
            self.fields[field_name].required = False
