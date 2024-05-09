from django import forms
from django.utils.text import slugify
from .. import models


class CompanyForm(
    forms.ModelForm,
):
    class Meta:
        model = models.Company
        fields = [
            'handler',
            'slug',
            'admins',
            'matrix_room_id',
        ]
        widgets = {
        }
        optional = [
        ]

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
