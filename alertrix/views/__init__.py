from django.shortcuts import render

from . import appservice
from . import company
from . import unit
from .. import models


def home(request):
    return render(
        request,
        'alertrix/home.html',
    )
