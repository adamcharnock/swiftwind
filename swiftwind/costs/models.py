from decimal import Decimal

from django.db import models
from django.db import transaction as db_transaction
from django.db.models import QuerySet
from django.utils import timezone
from django_smalluuid.models import SmallUUIDField
from django_smalluuid.models import uuid_default
from hordak.models import Transaction, Leg
from hordak.utilities.currency import Balance
from model_utils import Choices
from psycopg2._range import DateRange

from swiftwind.billing_cycle.models import BillingCycle
from .exceptions import CannotEnactUnenactableRecurringCostError, CannotRecreateTransactionOnRecurredCost, \
    NoSplitsFoundForRecurringCost, ProvidedBillingCycleBeginsBeforeInitialBillingCycle, \
    RecurringCostAlreadyEnactedForBillingCycle
from hordak.utilities.money import ratio_split


class RecurringCostQuerySet(models.QuerySet):

    def enact(self, as_of):
        costs = [cost for cost in self if cost.is_enactable(as_of)]
        for billing_cycle in BillingCycle.objects.filter(transactions_created=False, start_date__lte=as_of):
            for cost in costs:
                cost.enact(billing_cycle)


class RecurringCost(models.Model):
    """ Represents recurring costs and one-off costs

    Recurring costs recur indefinitely, or until `disabled` is set to `True`.

    One-off costs have a value for `total_billing_cycles` set. This value indicates
    how many billing cycles the one-off cost should be spread. After this point
    the recurring cost will be disabled.

    Additionally, the type field indicates how the cost should calculate the amount
    to be billed.

    A note on 'enacting': We use the term 'enact' to refer to the creation of a
    definite RecurredCost from the more conceptual RecurringCost. The former
    is the creator - and link to - the actual transactions created for the cost in a
    given billing cycle.
    """

    TYPES = Choices(
        (
            'normal',
            "We will not have spent this yet. We will estimate "
            "a fixed amount per billing cycle."
        ),
        (
            'arrears_balance',
            "We will have already spent this in the previous billing "
            "cycle, so bill the account's balance."),
        (
            'arrears_transactions',
            "We will have already spent this in the previous cycle, "
            "so bill the total amount spent in the previous cycle."
        ),
    )

    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    from_accounts = models.ManyToManyField('hordak.Account',
                                           through='costs.RecurringCostSplit',
                                           related_name='outbound_costs')
    to_account = models.ForeignKey('hordak.Account', related_name='inbound_costs')
    #: The disabled flag is mostly present for the benefit of the database checks & triggers.
    #: We could infer the disabled state from other values (billed amount, number of billing
    #: periods billed, etc), but checking this would make our triggers rather complex.
    disabled = models.BooleanField(default=False)
    # The amount to be billed per cycle for recurring costs, or the amount to spread
    # across cycles for one-off costs
    fixed_amount = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    total_billing_cycles = models.PositiveIntegerField(default=None, null=True, blank=True,
                                                       help_text='Stop billing after this many billing cycles.')
    type = models.CharField(max_length=20, choices=TYPES, default=TYPES.normal)
    #: May only be Null if disabled=True. Enforced by DB constraint.
    initial_billing_cycle = models.ForeignKey('billing_cycle.BillingCycle', null=True, blank=True)
    transactions = models.ManyToManyField(Transaction, through='costs.RecurredCost')

    objects = models.Manager.from_queryset(RecurringCostQuerySet)()

    @property
    def currency(self):
        # This is a simplification, but probably ok for now as swiftwind probably won't
        # need to deal with multiple currencies given its target audience
        return self.to_account.currencies[0]

    def get_amount(self, billing_cycle):
        return {
            RecurringCost.TYPES.normal: self.get_amount_normal,
            RecurringCost.TYPES.arrears_balance: self.get_amount_arrears_balance,
            RecurringCost.TYPES.arrears_transactions: self.get_amount_arrears_transactions,
        }[self.type](billing_cycle)

    def get_amount_normal(self, billing_cycle):
        """Get the amount due on the given billing cycle

        For regular recurring costs this is simply `fixed_amount`. For
        one-off costs this is the portion of `fixed_amount` for the given
        billing_cycle.
        """
        if self.is_one_off():
            billing_cycle_number = self._get_billing_cycle_number(billing_cycle)

            if billing_cycle_number > self.total_billing_cycles:
                # A future billing cycle after this one has ended
                return Decimal('0')
            else:
                # This is a current cycle. Split the amount into
                # equal parts then return the part for this cycle
                splits = ratio_split(
                    amount=self.fixed_amount,
                    ratios=[Decimal('1')] * self.total_billing_cycles,
                )
                return splits[billing_cycle_number - 1]
        else:
            # This is a none-one-off recurring cost, so the logic is simple
            return self.fixed_amount

    def get_amount_arrears_balance(self, billing_cycle):
        """Get the balance of to_account at the end of billing_cycle"""
        return self.to_account.balance(
            transaction__date__lt=billing_cycle.date_range.upper,
        )

    def get_amount_arrears_transactions(self, billing_cycle):
        """Get the sum of all transaction legs in to_account during given billing cycle"""
        return self.to_account.balance(
            transaction__date__lt=billing_cycle.date_range.upper,
            transaction__date__gte=billing_cycle.date_range.lower,
        )

    def get_billed_amount(self):
        """Get the total amount billed so far"""
        return Leg.objects.filter(transaction__recurred_cost__recurring_cost=self, amount__gt=0).sum_to_balance()

    def enact(self, billing_cycle):
        """Enact this RecurringCost for the given billing cycle

        This will:

          - Create a RecurredCost and the relevant Transactions & Transaction Legs
          - Mark this RecurringCost as disabled if this is its final billing cycle
        """
        as_of = billing_cycle.date_range.lower
        if not self.is_enactable(as_of):
            raise CannotEnactUnenactableRecurringCostError(
                "RecurringCost {} is unenactable.".format(self.uuid)
            )

        if self.has_enacted(billing_cycle):
            raise RecurringCostAlreadyEnactedForBillingCycle(
                'RecurringCost cost {} already enacted for {}'.format(self, billing_cycle)
            )

        with db_transaction.atomic():
            recurred_cost = RecurredCost(
                recurring_cost=self,
                billing_cycle=billing_cycle,
            )
            recurred_cost.make_transaction()
            recurred_cost.save()

        self.disable_if_done(billing_cycle)

    def disable_if_done(self, commit=True):
        """Set disabled=True if we have billed all we need to

        Will only have an effect on one-off costs.
        """
        if self._is_billing_complete() and not self.disabled:
            self.initial_billing_cycle = None
            self.disabled = True

            if commit:
                self.save()

    def is_enactable(self, as_of):
        """Can this RecurringCost be enacted"""
        return \
            not self.disabled and \
            not self._is_finished(as_of) and \
            self._is_ready(as_of) and \
            not self._is_billing_complete()

    def has_enacted(self, billing_cycle):
        """Has this recurring cost already enacted transactions for given billing cycle?"""
        return RecurredCost.objects.filter(
            recurring_cost=self,
            billing_cycle=billing_cycle,
        ).exists()

    def is_one_off(self):
        return bool(self.total_billing_cycles)

    def _is_ready(self, as_of):
        """Is the RecurringCost ready to be enacted as of the date `as_of`

        This determines if `as_of` precedes the start of `initial_billing_cycle`. If so,
        we should not be enacting this RecurringCost yet.

        Args:
            as_of (Date):
        """
        if self.is_one_off():
            return self.initial_billing_cycle.date_range.lower <= as_of
        else:
            return True

    def _is_finished(self, as_of):
        """Have the specified number of billing cycles been completed?

        If so, we should not be enacting this RecurringCost.
        """
        if self.is_one_off():
            last_billing_cycle = self.get_billing_cycles()[self.total_billing_cycles - 1]
            return last_billing_cycle.date_range.upper <= as_of
        else:
            return False

    def _is_billing_complete(self):
        """Has the specified `fixed_amount` been billed?

        If so, we should not be enacting this RecurringCost.
        """
        if self.is_one_off():
            return self.get_billed_amount() >= Balance(self.fixed_amount, self.currency)
        else:
            return False

    def _get_billing_cycle_number(self, billing_cycle):
        """Gets the 1-indexed number of the billing cycle relative to the provided billing cycle"""
        begins_before_initial_date = billing_cycle.date_range.lower < self.initial_billing_cycle.date_range.lower
        if begins_before_initial_date:
            raise ProvidedBillingCycleBeginsBeforeInitialBillingCycle(
                '{} precedes initial cycle {}'.format(billing_cycle, self.initial_billing_cycle)
            )

        billing_cycle_number = BillingCycle.objects.filter(
            date_range__contained_by=DateRange(
                self.initial_billing_cycle.date_range.lower,
                billing_cycle.date_range.upper,
                bounds='[]',
            ),
        ).count()

        return billing_cycle_number

    def get_billing_cycles(self):
        return BillingCycle.objects.filter(
            start_date__gte=self.initial_billing_cycle.date_range.lower
        )[:self.total_billing_cycles]


class RecurringCostSplitQuerySet(QuerySet):

    def split(self, amount):
        """Split the value given by amount according to the RecurringCostSplit's portions

        Args:
            amount (Decimal):

        Returns:
            list[(RecurringCostSplit, Decimal)]: A list with elements in the form (RecurringCostSplit, Decimal)
        """
        split_objs = list(self.all())
        if not split_objs:
            raise NoSplitsFoundForRecurringCost()

        portions = [split_obj.portion for split_obj in split_objs]

        split_amounts = ratio_split(amount, portions)
        return [
            (split_objs[i], split_amount)
            for i, split_amount
            in enumerate(split_amounts)
        ]


class RecurringCostSplit(models.Model):
    """Represents how a recurring cost should be split between accounts (i.e. housemates)"""
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    recurring_cost = models.ForeignKey(RecurringCost, related_name='splits')
    from_account = models.ForeignKey('hordak.Account')
    portion = models.DecimalField(max_digits=13, decimal_places=2, default=1)

    objects = models.Manager.from_queryset(RecurringCostSplitQuerySet)()

    class Meta:
        base_manager_name = 'objects'
        unique_together = (
            ('recurring_cost', 'from_account'),
        )


class RecurredCost(models.Model):
    """A record of a recurring cost which has been enacted.

    Links together the RecurringCost, BillingCycle, and Transaction.
    """
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    recurring_cost = models.ForeignKey(RecurringCost, related_name='recurrences')
    billing_cycle = models.ForeignKey('billing_cycle.BillingCycle', related_name='recurring_costs')
    transaction = models.OneToOneField(Transaction, related_name='recurred_cost', unique=True)

    class Meta:
        unique_together = (
            # A RecurringCost should only be enacted once per billing cycle
            ('recurring_cost', 'billing_cycle'),
        )

    def make_transaction(self):
        """Create the transaction for this RecurredCost

        May only be used to create the RecurredCost's initial transaction.

        Returns:
            Transaction: The created transaction, also assigned to self.transaction
        """
        try:
            self.transaction
        except Transaction.DoesNotExist:
            pass
        else:
            raise CannotRecreateTransactionOnRecurredCost()

        self.transaction = Transaction.objects.create(
            description='Created by recurring cost: {}'.format(self.recurring_cost)
        )

        amount = self.recurring_cost.get_amount(self.billing_cycle)
        # Use the SplitManager's custom queryset's split() method to get the
        # amount to be billed for each split
        splits = self.recurring_cost.splits.all().split(amount)

        # Create the transaction leg for the outbound funds
        # (normally to an expense account)
        self.transaction.legs.add(Leg.objects.create(
            transaction=self.transaction,
            amount=amount * -1,
            account=self.recurring_cost.to_account,
        ))

        for split, split_amount in splits:
            # Create the transaction legs for the inbound funds
            # (from housemate accounts)
            self.transaction.legs.add(Leg.objects.create(
                transaction=self.transaction,
                amount=split_amount,
                account=split.from_account,
            ))

        return self.transaction


