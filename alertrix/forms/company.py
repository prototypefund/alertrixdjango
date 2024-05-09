from django import forms
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

    def __init__(
            self,
            data=None,
            *args, **kwargs
    ):
        super().__init__(
            data=data,
            *args, **kwargs
        )
