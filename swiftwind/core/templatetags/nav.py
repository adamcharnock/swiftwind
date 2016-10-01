from django import template
from hordak.models import Account, StatementLine

register = template.Library()

@register.simple_tag
def housemate_accounts():
    return Account.objects.filter(children=None).filter(parent__name='Housemate Income')


@register.simple_tag
def other_accounts():
    return Account.objects.filter(children=None).exclude(parent__name='Housemate Income')


@register.simple_tag
def total_unreconciled():
    return StatementLine.objects.filter(transaction=None).count()
