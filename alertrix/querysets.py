import logging
from typing import Any
from typing import Iterable
from typing import List

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from django.db.models.query import QuerySet
from matrixappservice.models import *

from . import models


direct_messages = Room.objects.filter(
    room_id__in=Event.objects.filter(
        Q(
            content__membership='invite',
            content__is_direct=True,
        ) | Q(
            content__membership='join',
            unsigned__prev_content__is_direct=True,
        ),
    ).values_list(
        'room__room_id',
        flat=True,
    ),
)


def get_direct_message_for(
        *users: str,
        valid_memberships: List[str] = None,
) -> Room:
    if valid_memberships is None:
        valid_memberships = [
            'join',
        ]
    queryset = models.DirectMessage.objects.get_queryset()
    for user in users:
        queryset = queryset.intersection(
            direct_messages.filter(
                room_id__in=Event.objects.filter(
                    content__membership__in=valid_memberships,
                    state_key=user,
                ).values_list(
                    'room__room_id',
                    flat=True,
                ),
            )
        )
    try:
        return queryset.get()
    except Room.MultipleObjectsReturned as e:
        logging.error(
            'returned too many rooms: %(room_list)s' % {
                'room_list': str(queryset),
            },
        )
        raise e


def get_companies_for_unit(
        unit: [
            Iterable,
            List[str],
            QuerySet,
            Room,
            models.Unit,
        ],
):
    return models.Company.objects.filter(
        room_id__in=Event.objects.filter(
            type='%(prefix)s.company.unit' % {
                'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
            },
            **(
                dict(
                    state_key=unit.room_id,
                )
                if type(unit) is Room
                else
                dict(
                    state_key__in=unit,
                )
                if '__iter__' in dir(unit)
                else
                dict(
                    state_key__in=unit.values_list(
                        'state_key',
                        flat=True,
                    ),
                )
                if type(unit) is QuerySet
                else
                dict()
            ),
        ).values_list(
            'room__room_id',
            flat=True,
        ),
    )


def get_units_for_company(
        company: Room,
):
    return models.Unit.objects.get_queryset().filter(
        room_id__in=Event.objects.filter(
            type='%(prefix)s.company.unit' % {
                'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
            },
            state_key__isnull=False,
            room=company,
        ).values_list(
            'state_key',
            flat=True,
        ),
    )
