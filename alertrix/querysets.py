import logging
from typing import List

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from matrixappservice.models import *


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
    queryset = direct_messages
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


async def aget_direct_message_for(
        *users: str,
        valid_memberships: List[str] = None,
) -> Room:
    return await sync_to_async(get_direct_message_for)(
        *users,
        valid_memberships=valid_memberships,
    )


companies = Room.objects.filter(
    room_id__in=Event.objects.filter(
        type='%(prefix)s.company' % {
            'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
        },
        state_key__isnull=False,
    ).values_list(
        'room__room_id',
        flat=True,
    ),
)


def get_companies_for_unit(
        unit: Room,
):
    return companies.filter(
        room_id__in=Event.objects.filter(
            type='%(prefix)s.company.unit' % {
                'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
            },
        ).values_list(
            'room__room_id',
            flat=True,
        ),
    )


units = Room.objects.filter(
    room_id__in=Event.objects.filter(
        type='%(prefix)s.company.unit' % {
            'prefix': settings.ALERTRIX_STATE_EVENT_PREFIX,
        },
        content__isnull=False,
        state_key__isnull=False,
        room__in=companies,
    ).values_list(
        'state_key',
        flat=True,
    ),
)


def get_units_for_company(
        company: Room,
):
    return units.filter(
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
