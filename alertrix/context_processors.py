from django.conf import settings


def service_name(request):
    return {
        'service_name': settings.SERVICE_NAME,
    }


def emoticons(request):
    return {
        'emoticon_company': settings.ALERTRIX_COMPANY_EMOTICON,
        'emoticon_unit': settings.ALERTRIX_UNIT_EMOTICON,
    }
