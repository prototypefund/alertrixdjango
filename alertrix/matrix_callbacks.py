import nio
from django.conf import settings

from . import callbacks
from alertrix.command_line_interface.cli import chat_cli

matrix_callbacks = [
    (callbacks.onboarding.ensure_encryption, nio.RoomMessage),
    (callbacks.encryption.verify_all_devices, nio.Event),
    (callbacks.onboarding.on_room_invite, nio.InviteMemberEvent),
    (callbacks.onboarding.on_room_join, nio.RoomMemberEvent),
    (chat_cli, nio.RoomMessageText),
    (callbacks.directmessage.on_left_direct_message, nio.RoomMemberEvent),
    (
        callbacks.RecursiveMessageHandler(
            attribute_prefix=settings.ALERTRIX_MESSAGE_EVENT_PREFIX,
            callbacks=callbacks.alertrix.alertrix_callbacks,
        ),
        nio.RoomMessage,
    ),
]
