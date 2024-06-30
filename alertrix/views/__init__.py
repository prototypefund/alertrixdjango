from django.shortcuts import render

from . import appservice
from . import company
from . import unit
from .. import models


def home(request):
    return render(
        request,
        'alertrix/home.html',
        context={
            'main_user': models.MainApplicationServiceKey.objects.get(
                id=1,
            ).service.get_user(),
        },
    )
