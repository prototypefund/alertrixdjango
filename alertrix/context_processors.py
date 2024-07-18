from django.conf import settings


def service_name(request):
    return {
        'service_name': settings.SERVICE_NAME,
    }
