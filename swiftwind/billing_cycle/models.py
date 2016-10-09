from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields import DateRangeField
from django.db import models
from django.db import transaction as db_transaction
from django.db.models.functions import Lower, Upper
from django.utils.datetime_safe import datetime, date
from django_smalluuid.models import uuid_default, SmallUUIDField
from django.conf import settings

from swiftwind.billing_cycle.exceptions import CannotPopulateForDateOutsideExistingCycles
from .cycles import get_billing_cycle


class BillingCycleManager(models.Manager):

    def get_queryset(self):
        queryset = super(BillingCycleManager, self).get_queryset()
        return queryset\
            .annotate(start_date=Lower('date_range'))\
            .annotate(end_date=Upper('date_range'))

    def enactable(self, as_of):
        """Find all billing cycles that should be enacted

        This consists of any billing cycle that has not had transactions created
        for it, and has a start date prior to `as_of`.
        """
        return self.filter(
            transactions_created=False,
            start_date__lte=as_of,
        )

    def as_of(self, date):
        return self.get(start_date__lte=date, end_date__gt=date)


class BillingCycle(models.Model):
    # TODO: Currently does not support changing of billing-cycle type (i.e. monthly/weekly)
    #       once data has been created
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    date_range = DateRangeField(
        db_index=True,
        help_text='The start and end date of this billing cycle. '
                  'May not overlay with any other billing cycles.'
    )
    transactions_created = models.BooleanField(
        default=False,
        help_text='Have transactions been created for this billing cycle?'
    )

    objects = BillingCycleManager()

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
        """Populate the table with billing cycles starting from `as_of`

        Args:
            as_of (date): The date at which to being the populating
            delete (bool): Should future billing cycles be deleted?


        """
        billing_cycle_helper = get_billing_cycle()
        billing_cycles_exist = BillingCycle.objects.exists()

        try:
            current_billing_cycle = BillingCycle.objects.as_of(date=as_of)
        except BillingCycle.DoesNotExist:
            current_billing_cycle = None

        # If no cycles exist then disable the deletion logic
        if not billing_cycles_exist:
            delete = False

        # Cycles exist, but a date has been specified outside of them
        if billing_cycles_exist and not current_billing_cycle:
            raise CannotPopulateForDateOutsideExistingCycles()

        # Omit the current billing cycle if we are deleting (as
        # deleting the current billing cycle will be a Bad Idea)
        omit_current = (current_billing_cycle and delete)

        stop_date = as_of + relativedelta(years=settings.SWIFTWIND_BILLING_CYCLE_YEARS)
        date_ranges = billing_cycle_helper.generate_date_ranges(as_of, stop_date=stop_date, omit_current=omit_current)
        date_ranges = list(date_ranges)

        beginning_date = date_ranges[0][0]

        with db_transaction.atomic():

            if delete:
                # Delete all the future unused transactions
                cls.objects.filter(start_date__gte=beginning_date).delete()

            for start_date, end_date in date_ranges:
                exists = BillingCycle.objects.filter(date_range=(start_date, end_date)).exists()
                if exists:
                    if delete:
                        raise Exception(
                            'It should not be possible to get here as future billing cycles have just been deleted'
                        )
                    else:
                        # We're updating, so we can just ignore cycles that already exist
                        pass
                else:
                    BillingCycle.objects.create(
                        date_range=(start_date, end_date),
                    )

    def get_next(self):
        return BillingCycle.objects.filter(date_range__gt=self.date_range).order_by('date_range')[0]

    def get_previous(self):
        return BillingCycle.objects.filter(date_range__lt=self.date_range).order_by('-date_range')[0]


