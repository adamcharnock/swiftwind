from dateutil.relativedelta import relativedelta
from django.contrib.postgres.fields import DateRangeField
from django.core.mail import send_mail
from django.db import models, transaction
from django.db import transaction as db_transaction
from django.db.models.functions import Lower, Upper
from django.urls.base import reverse
from django.utils import formats
from django.utils.datetime_safe import datetime, date
from django_smalluuid.models import uuid_default, SmallUUIDField
from django.conf import settings
from pytz import UTC

from hordak.models import Transaction
from swiftwind.billing_cycle.exceptions import CannotPopulateForDateOutsideExistingCycles
from swiftwind.costs.exceptions import CannotEnactUnenactableRecurringCostError, \
    RecurringCostAlreadyEnactedForBillingCycle
from swiftwind.settings.models import Settings
from swiftwind.housemates.models import Housemate
from swiftwind.utilities.site import get_site_root

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
    statements_sent = models.BooleanField(
        default=False,
        help_text='Have we sent housemates their statements for this billing cycle?'
    )

    objects = BillingCycleManager()

    class Meta:
        ordering = ['date_range']

    def __str__(self):
        return 'Cycle starting {}'.format(formats.localize(self.date_range.lower, use_l10n=True))

    def __repr__(self):
        return 'BillingCycle <{}>'.format(self.date_range)

    @classmethod
    def populate(cls, as_of=None):
        """Ensure the next X years of billing cycles exist
        """
        return cls._populate(as_of=as_of or date.today(), delete=True)

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
            as_of (date): The date at which to begin the populating
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
        """Get the billing cycle after this one. May return None"""
        return BillingCycle.objects.filter(date_range__gt=self.date_range).order_by('date_range').first()

    def get_previous(self):
        """Get the billing cycle prior to this one. May return None"""
        return BillingCycle.objects.filter(date_range__lt=self.date_range).order_by('date_range').last()

    def is_reconciled(self):
        """Have transactions been imported and reconciled for this billing cycle?"""
        from hordak.models import StatementImport, StatementLine
        since = datetime(
            self.date_range.lower.year,
            self.date_range.lower.month,
            self.date_range.lower.day,
            tzinfo=UTC
        )
        if not StatementImport.objects.filter(timestamp__gte=since).exists():
            # No import done since the end of the above billing cycle, and reconciliation
            # requires an import. Therefore reconciliation can not have been done
            return False

        if StatementLine.objects.filter(
            transaction__isnull=True,
            date__gte=self.date_range.lower,
            date__lt=self.date_range.upper
        ).exists():
            # There are statement lines for this period which have not been reconciled
            return False

        return True

    def notify_housemates(self):
        """Notify housemates in one of two ways:

        1. Reconciliation is required before statements can be sent
        2. Send a statement
        """
        if self.is_reconciled():
            self.send_statements()
        else:
            self.send_reconciliation_required()

    def send_reconciliation_required(self):
        from swiftwind.accounts.views import ReconciliationRequiredEmailView

        for housemate in Housemate.objects.filter(user__is_active=True):
            html = ReconciliationRequiredEmailView.get_html()
            send_mail(
                subject='Reconciliation required'.format(),
                message='See {}{}'.format(
                    get_site_root(),
                    reverse('accounts:housemate_reconciliation_required_email')
                ),
                from_email=Settings.objects.get().email_from_address,
                recipient_list=[housemate.user.email],
                html_message=html,
            )

    def can_create_transactions(self):
        """Can we create the transactions

        We can only do this if the previous cycle has been reconciled,
        as some costs may depend upon it to calculate their amounts.
        """
        previous = self.get_previous()
        return not previous or previous.is_reconciled()

    def can_send_statements(self):
        return self.can_create_transactions() and self.transactions_created

    @transaction.atomic()
    def send_statements(self, force=False):
        from swiftwind.accounts.views import StatementEmailView

        should_send = force or (not self.statements_sent and self.transactions_created)
        if not should_send:
            return False

        for housemate in Housemate.objects.filter(user__is_active=True):
            html = StatementEmailView.get_html(
                uuid=housemate.uuid,
                date=str(self.date_range.lower)
            )
            send_mail(
                subject='{}, your house statement for {}'.format(
                    housemate.user.first_name or housemate.user.username,
                    self.date_range.upper,
                ),
                message='See {}{}'.format(
                    get_site_root(),
                    reverse('accounts:housemate_statement_email',
                            args=[housemate.uuid, str(self.date_range.lower)]
                            )
                ),
                from_email=Settings.objects.get().email_from_address,
                recipient_list=[housemate.user.email],
                html_message=html,
            )

    @transaction.atomic()
    def enact_all_costs(self):
        from swiftwind.costs.models import RecurringCost

        for recurring_cost in RecurringCost.objects.all():
            try:
                recurring_cost.enact(self)
            except (CannotEnactUnenactableRecurringCostError, RecurringCostAlreadyEnactedForBillingCycle):
                pass

        self.transactions_created = True
        self.save()

    def reenact_all_costs(self):
        from swiftwind.costs.models import RecurringCost, RecurredCost

        with transaction.atomic():
            Transaction.objects.filter(recurred_cost__billing_cycle=self).delete()
            RecurredCost.objects.filter(billing_cycle=self).delete()
            self.transactions_created = False
            self.save()

            for recurring_cost in RecurringCost.objects.all():
                recurring_cost.disabled = False
                if not recurring_cost.is_enactable(self.start_date):
                    continue

                recurring_cost.save()
                recurring_cost.enact(self, disable_if_done=False)

            self.transactions_created = True
            self.save()

        for recurring_cost in RecurringCost.objects.all():
            recurring_cost.disable_if_done(self)
