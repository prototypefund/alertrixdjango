import nio

from . import callbacks

matrix_callbacks = [
    (callbacks.onboarding.on_room_invite, nio.InviteMemberEvent),
    (callbacks.onboarding.add_widget_to_chat, nio.RoomMessageText),
]
