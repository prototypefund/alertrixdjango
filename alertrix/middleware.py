from django.contrib.auth import get_user_model
from django.contrib.auth import login


class WidgetWatcher:
    def __init__(self, get_response):
        self.get_response = get_response

    def get_widget_response(
            self,
            request,
            widget_id,
            *args, **kwargs,
    ):
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
