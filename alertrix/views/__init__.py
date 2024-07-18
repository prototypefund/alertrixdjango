import matrixappservice
from django.contrib import messages

from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from matrixappservice import models as mas_models
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
            'units': models.Unit.objects.filter(
                matrix_room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_units': models.Unit.objects.all().count(),
            'companies': models.Company.objects.filter(
                matrix_room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_companies': models.Company.objects.all().count(),
        },
    )
