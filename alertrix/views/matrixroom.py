import nio
from django.contrib import messages
from django.utils.translation import gettext_lazy as _


class CreateMatrixRoom(
):
    """
    Parent CreateView to create MatrixRoom objects.
    """

    def get_form_kwargs(self):
        kwargs = {
            'user': self.request.user,
            **super().get_form_kwargs(),
        }
        return kwargs
