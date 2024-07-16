import matrixappservice
from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from . import appservice
from . import company
from . import unit
from .. import models


def home(request):
    main_user = None
    try:
        main_user = models.MainApplicationServiceKey.objects.get(id=1).service.mainuserkey.user
    except models.MainApplicationServiceKey.DoesNotExist:
        messages.error(
            request,
            _('no main application service has been set'),
        )
    except matrixappservice.models.ApplicationServiceRegistration.mainuserkey.RelatedObjectDoesNotExist:
        messages.error(
            request,
            _('no main user set for the main application service'),
        )
    return render(
        request,
        'alertrix/home.html',
        context={
            'main_user': main_user,
        },
    )
