import locale

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='abs')
def abs_val(value):
    return abs(value)


@register.filter()
def currency(value):
    locale.setlocale(locale.LC_ALL, 'en_GB.UTF-8')
    return locale.currency(value, grouping=True)


@register.filter(is_safe=True)
def color_currency(value, flip=False):
    value = value or 0
    if value > 0:
        css_class = 'neg' if flip else 'pos'
    elif value < 0:
        css_class = 'pos' if flip else 'neg'
    else:
        css_class = 'zero'
    out = """<div class="%s">%s</div>""" % (css_class, currency(value))
    return mark_safe(out)


@register.filter(is_safe=True)
def color_currency_inv(value):
    return color_currency(value, flip=True)

@register.filter(is_safe=True)
def negative(value):
    value = value or 0
    return abs(value) * -1
