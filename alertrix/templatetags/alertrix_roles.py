from django import template

from .. import querysets


register = template.Library()


@register.filter
def is_company(room):
    return room in querysets.companies


@register.filter
def is_unit(room):
    return room in querysets.units
