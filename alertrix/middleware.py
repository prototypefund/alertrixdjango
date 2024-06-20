

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
        return response

    def __call__(self, request, *args, **kwargs):
        widget_id = None
        if 'widgetId' in request.GET:
            widget_id = request.GET['widgetId']
        if widget_id:
            response = self.get_widget_response(
                request,
                widget_id,
                *args, **kwargs
            )
        else:
            response = self.get_response(request)
        return response
