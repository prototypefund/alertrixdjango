import json
import secrets
import string

import matrixappservice
import nio
from asgiref.sync import async_to_sync
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import loader
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from matrixappservice import models as mas_models
from matrixappservice.database import models as database

from . import appservice
from . import company
from . import unit
from .. import forms
from .. import models
from .. import querysets


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
            'units': querysets.units.filter(
                room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership='join',
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_units': querysets.units.count(),
            'companies': querysets.companies.filter(
                room_id__in=mas_models.Event.objects.filter(
                    type='m.room.member',
                    content__membership__in=['invite', 'join'],
                    state_key=request.user.matrix_id,
                ).values_list('room_id', flat=True),
            ) if request.user.is_authenticated else list(),
            'n_total_companies': querysets.companies.count(),
        },
    )
