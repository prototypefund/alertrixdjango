import secrets
import string

from django.conf import settings


def get_token(length: int = None):
    if length is None:
        try:
            length = settings.ACCOUNTS_REGISTRATION_TOKEN_LENGTH
        except AttributeError:
            length = 8
    return ''.join(
        [
            secrets.choice(string.ascii_lowercase + string.digits)
            for _ in range(length)
        ]
    )
