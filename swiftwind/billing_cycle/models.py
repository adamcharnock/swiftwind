from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields import DateRangeField
from django.db import models
from django.db import transaction as db_transaction
from django.utils.datetime_safe import datetime, date
from django_smalluuid.models import uuid_default, SmallUUIDField
from django.conf import settings
from psycopg2._range import DateRange

from swiftwind.billing_cycle.cycles import get_billing_cycle


class BillingCycle(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    date_range = DateRangeField(
        help_text='The start and end date of this billing cycle. '
                  'May not overlay with any other billing cycles.'
    )
    transactions_created = models.BooleanField(
        default=False,
        help_text='Have transactions been created for this billing cycle?'
    )

    class Meta:
        ordering = ['date_range']

    def __str__(self):
        return 'BillingCycle <{}>'.format(self.date_range)

    @classmethod
    def populate(cls):
        """Ensure the next X years of billing cycles exist
        """
        return cls._populate(as_of=date.today(), delete=True)

    @classmethod
    def repopulate(cls):
        """Create the next X years of billing cycles

        Will delete any billing cycles which are in the future
        """
        return cls._populate(as_of=date.today(), delete=False)

    @classmethod
    def _populate(cls, as_of=None, delete=False):
        if as_of is None:
            as_of = datetime.now().date()

        billing_cycle = get_billing_cycle()
        stop_date = as_of + relativedelta(years=settings.SWIFTWIND_BILLING_CYCLE_YEARS)
        date_ranges = billing_cycle.generate_date_ranges(as_of, stop_date=stop_date)

        with db_transaction.atomic():

            if delete:
                # Delete all the future unused transactions
                cls.objects.filter(
                    date_range__fully_gt=DateRange(as_of, as_of, bounds='[]')
                ).delete()

            # Now recreate the upcoming billing cycles
            for start_date, end_date in date_ranges:
                if not delete:
                    exists = BillingCycle.objects.filter(date_range=[start_date, end_date]).count()
                    if exists:
                        # If we are not deleting (i.e. updating only), then don't
                        # create this BillingCycle if one already exists
                        continue

                BillingCycle.objects.create(
                    date_range=(start_date, end_date),
                )


