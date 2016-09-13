import calendar
from datetime import date
from decimal import Decimal
from django.core.urlresolvers import reverse, NoReverseMatch

from django.utils.http import is_safe_url
from django.shortcuts import redirect


# All of these functions should be considered for removal
# unless used following the django-hordak refactoring


def end_of_month(for_date):
    if not for_date:
        for_date = date.today()
    day = calendar.monthrange(for_date.year, for_date.month)[1]
    return date(for_date.year, for_date.month, day)


def month_delta(date, months):
    m, y = (date.month+months) % 12, date.year + ((date.month)+months-1) // 12
    if not m:
        m = 12
    d = min(date.day, [31, 29 if y%4==0 and not y%400==0 else 28,31,30,31,30,31,31,30,31,30,31][m-1])
    return date.replace(day=d, month=m, year=y)


def ratio_split(in_value, ratios, precision=2):
    ratio_total = sum(ratios)
    divided_value = in_value / ratio_total
    values = []
    for ratio in ratios:
        value = divided_value * ratio
        values.append(value)

    # Now round the values, keeping track of the bits we cut off
    rounded = [v.quantize(Decimal('0.01')) for v in values]
    remainders = [v - rounded[i] for i, v in enumerate(values)]
    remainder = sum(remainders)
    # Give the last person the (positive or negative) remainder
    rounded[-1] = (rounded[-1] + remainder).quantize(Decimal('0.01'))

    return rounded

def redirect_default(request, to=None, next_param='next'):
    """
        Perform a redirect, getting the url from one of the following
            - A request parameter specified by the parameter `next_param` (default='next')
            - The url/url-name/model specified by `to`
            - The request http referrer
            - The root url '/'
    """
    def check(url):
        if not isinstance(url, str):
            # Probably a model
            return url
        if not url.startswith('/'):
            # Probably a URL pattern
            try:
                return reverse(to)
            except NoReverseMatch:
                pass
        if not is_safe_url(url=url, host=request.get_host()):
            return None
        else:
            return url

    next = check(request.GET.get(next_param, None))
    next = next or check(to)
    next = next or check(request.META.get('HTTP_REFERRER'))
    next = next or '/'

    return redirect(next)
