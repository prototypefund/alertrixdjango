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
) -> Room:
    queryset = direct_messages
    for user in users:
        queryset = queryset.intersection(
            direct_messages.filter(
                room_id__in=Event.objects.filter(
                    content__membership__in=['invite', 'join'],
                    state_key=user,
                ).values_list(
                    'room__room_id',
                    flat=True,
                ),
            )
        )
    return queryset.get()


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
