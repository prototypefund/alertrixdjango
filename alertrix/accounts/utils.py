import secrets
import string
import aiohttp

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


async def get_server_well_known(server_name: str) -> dict:
    async with aiohttp.ClientSession() as session:
        response = await session.get(''.join([
            'http://',
            server_name,
            '/.well-known/matrix/client',
        ]))
        data = await response.json()
    return data
