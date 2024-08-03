from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.utils import timezone

from . import models


class WidgetWatcher:
    """
    If you want to make use of this middleware, you should be aware of the side effects
    of making you website embeddable into iframes.

    In your :code:`settings.py` You need to weaken your security settings by using

    .. code-block :: python

        SESSION_COOKIE_SAMESITE = 'None'
        SESSION_COOKIE_SECURE = True

    but you should increase security by using

    .. code-block :: python

        CSP_FRAME_ANCESTORS = (
            "'self'",
            "vector://vector",  # This is the name of the parent frame of element.
        )
        CSP_IMG_SRC = (
            "'self'",
            # if you use a cdn for images, you would need to add that here ("https://cdn.domain.tld")
        )
        CSP_STYLE_SRC = (
            "'self'",
            # if you use a cdn for stylesheets, you would need to add that here ("https://cdn.domain.tld")
        )
        CSP_SCRIPT_SRC = (
            "'self'",
            # if you use a cdn for scripts, you would need to add that here ("https://cdn.domain.tld")
        )

    """
    def __init__(self, get_response):
        self.get_response = get_response

    def get_widget_response(
            self,
            request,
            widget_id,
            *args, **kwargs,
    ):
        widget = get_object_or_404(
            models.Widget,
            id=widget_id,
        )
        if not widget.first_use_timestamp:
            widget.first_use_timestamp = timezone.now()
            widget.save()
            login(
                request,
                get_user_model().objects.get(
                    matrix_id=widget.user_id,
                ),
            )
        response = self.get_response(request, *args, **kwargs)
        if 'widgetId' in request.GET:
            if (
                    'widgetId' in request.COOKIES and request.GET['widgetId'] != request.COOKIES['widgetId']
                    or widget_id not in request.COOKIES
            ):
                response.set_cookie(
                    'widgetId',
                    request.GET['widgetId'],
                    secure=True,
                    httponly=True,
                    samesite="none",
                )
        return response

    def __call__(self, request, *args, **kwargs):
        widget_id = None
        if 'widgetId' in request.GET:
            widget_id = request.GET['widgetId']
        if not widget_id and 'widgetId' in request.COOKIES:
            widget_id = request.COOKIES['widgetId']
        if widget_id:
            response = self.get_widget_response(
                request,
                widget_id,
                *args, **kwargs
            )
        else:
            response = self.get_response(request)
        return response
