import six
from django import template

register = template.Library()


@register.filter
def partition(list_, columns=2):
    """
    Break a list into ``columns`` number of columns.
    """

    iter_ = iter(list_)
    columns = int(columns)
    rows = []

    while True:
        row = []
        for column_number in range(1, columns + 1):
            try:
                value = six.next(iter_)
            except StopIteration:
                pass
            else:
                row.append(value)

        if not row:
            return rows
        rows.append(row)

@register.filter
def short_name(name):
    bits = (name or '').split(' ')
    if len(bits) == 0:
        return name
    else:
        first = bits[0]
        last = bits[-1]
        if last:
            # First + Initial
            return ' '.join([first, last[0]])
        else:
            # No last name, just give the first name
            return first
