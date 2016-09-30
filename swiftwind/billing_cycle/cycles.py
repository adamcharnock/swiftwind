import functools
from copy import copy

from dateutil.relativedelta import relativedelta
from django.utils.datetime_safe import date
from django.utils.module_loading import import_string
from django.conf import settings


@functools.lru_cache()
def get_billing_cycle():
    """

    Returns:
        BaseCycle:
    """
    return import_string(settings.SWIFTWIND_BILLING_CYCLE)()


class BaseCycle(object):

    def get_next_cycle_start_date(self, as_of, inclusive):
        """Get the starting date of the next cycle following `as_of`

        Args:
            as_of (date):
            inclusive (bool): May the start date be the specified by `as_of`
                              (True), or must it come after (False)
        """
        raise NotImplemented()

    def get_cycle_end_date(self, start_date):
        """Get the end date for a cycle which begins on `start_date`

        Args:
            start_date (date):
        """
        raise NotImplemented()

    def generate_date_ranges(self, as_of, inclusive=False, stop_date=None):
        """


        Args:
            as_of (date): Begin generating ranges on the first start date after `as_of`
            inclusive (bool): May the first start date be the specified by `as_of`?
            stop_date (date): Stop iterating after this date. Will generate results
                              infinitely if None.
        """
        while True:
            start_date = self.get_next_cycle_start_date(as_of, inclusive)
            end_date = self.get_cycle_end_date(start_date)
            as_of = end_date
            inclusive = True

            if stop_date and start_date > stop_date:
                # Gone far enough now, time to stop generating
                raise StopIteration()

            yield start_date, end_date


class Monthly(BaseCycle):

    def get_next_cycle_start_date(self, as_of, inclusive):
        if inclusive and as_of.day == 1:
            return copy(as_of)
        else:
            return date(year=as_of.year, month=as_of.month + 1, day=1)

    def get_cycle_end_date(self, start_date):
        next_month = start_date + relativedelta(months=1)
        return date(
            year=next_month.year,
            month=next_month.month,
            day=1,
        )
