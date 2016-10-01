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
    bits = name.split(' ')
    if len(bits) == 0:
        return name
    else:
        return ' '.join([bits[0], bits[-1][0]])
