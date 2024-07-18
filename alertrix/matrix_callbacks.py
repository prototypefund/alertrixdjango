import nio
from django.conf import settings

from . import callbacks

matrix_callbacks = [
    (callbacks.onboarding.ensure_encryption, nio.RoomMessage),
    (callbacks.encryption.verify_all_devices, nio.RoomMemberEvent),
    (callbacks.onboarding.on_room_invite, nio.InviteMemberEvent),
    (callbacks.onboarding.add_widget_to_chat, nio.RoomMessageText),
    (callbacks.directmessage.on_left_direct_message, nio.RoomMemberEvent),
]
