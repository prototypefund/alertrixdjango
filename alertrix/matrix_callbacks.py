import nio

from . import callbacks

matrix_callbacks = [
    (callbacks.onboarding.on_room_invite, nio.InviteMemberEvent),
]
