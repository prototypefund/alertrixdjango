from django.utils.translation import gettext_lazy as _
from django import forms


class MatrixRoomForm(
    forms.Form,
):
    class Meta:
        fields = [
            'name',
            'description',
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
            'matrix_room_id',
        ]
        advanced = [
            'matrix_room_id',
        ]
    name = forms.CharField(
        label=_('name'),
        widget=forms.TextInput(
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
            if field_name not in self.fields:
                continue
            self.fields[field_name].required = False
        for field_name in self.Meta.advanced:
            if field_name not in self.fields:
                continue
            self.fields[field_name].widget.attrs['class'] = 'advanced'


class MatrixRoomCreateForm(
    MatrixRoomForm,
):
    class Meta(MatrixRoomForm.Meta):
        fields = MatrixRoomForm.Meta.fields
        advanced = MatrixRoomForm.Meta.advanced + [
            'federate',
        ]
    federate = forms.BooleanField(
        label=_('federate'),
        initial=True,
        required=False,
    )
