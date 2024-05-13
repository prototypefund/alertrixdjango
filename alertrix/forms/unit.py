from django import forms
from django.utils.translation import gettext_lazy as _
import matrixappservice.models
from . import matrixroom
from .. import models


class UnitForm(
    matrixroom.MatrixRoomForm,
):
    class Meta(matrixroom.MatrixRoomForm.Meta):
        model = models.Unit
