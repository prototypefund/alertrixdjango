from importlib import import_module

from django.conf import settings
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest


def get_request(
        **kwargs,
):
    request = HttpRequest()

    # manually applying middleware
    # https://github.com/django/django/blob/fd1dd767783b5a7ec1a594fcc5885e7e4178dd26/django/contrib/sessions/middleware.py#L18
    engine = import_module(settings.SESSION_ENGINE)
    session_store = engine.SessionStore
    session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
    request.session = session_store(session_key)
    # https://github.com/django/django/blob/62039659603ca0fa2df796d1732c4b414549c52b/django/contrib/messages/middleware.py#L12
    request._messages = default_storage(request)

    request.__dict__.update(
        **kwargs,
    )
    return request
