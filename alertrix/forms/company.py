from django import forms
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
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
