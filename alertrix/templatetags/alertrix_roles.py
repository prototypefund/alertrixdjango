from django import template

from .. import querysets


register = template.Library()


@register.filter
def is_company(room):
    return room in querysets.companies
