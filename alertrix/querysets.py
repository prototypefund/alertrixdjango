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
