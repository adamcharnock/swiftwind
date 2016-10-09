from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db import transaction as db_transaction
from django.db.models import QuerySet
from django.utils import timezone
from django_smalluuid.models import SmallUUIDField
from django_smalluuid.models import uuid_default
from hordak.models import Transaction, Leg
from model_utils import Choices

from .exceptions import CannotEnactUnenactableRecurringCostError, CannotRecreateTransactionOnRecurredCost, \
    NoSplitsFoundForRecurringCost
from swiftwind.utilities.splitting import ratio_split


class RecurringCost(models.Model):
    """ Represents recurring costs and one-off costs

    Recurring costs recur indefinitely, or until `disabled` is set to `True`.

    One-off costs have a value for `total_billing_cycles` set. This value indicates
    how many billing cycles the one-off cost should be spread. After this point
    the recurring cost will be disabled.
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
    disabled = models.BooleanField(default=False)
    # The amount to be billed per cycle for recurring costs, or the amount to spread
    # across cycles for one-off costs
    fixed_amount = models.DecimalField(max_digits=13, decimal_places=2)
    total_billing_cycles = models.PositiveIntegerField(default=None, null=True, blank=True,
                                                       help_text='Stop billing after this many billing cycles.')
    type = models.CharField(max_length=20, choices=TYPES, default=TYPES.normal)
    transactions = models.ManyToManyField(Transaction, through='costs.RecurredCost')

    def save(self, *args, **kwargs):
        # TODO: Check that disabled=True if is_enactable()=False
        return super(RecurringCost, self).save(*args, **kwargs)

    def get_amount(self, billing_cycle):
        return {
            RecurringCost.TYPES.normal: self.get_amount_normal,
            RecurringCost.TYPES.arrears_balance: self.get_amount_arrears_balance,
            RecurringCost.TYPES.arrears_transactions: self.get_amount_arrears_transactions,
        }[self.type](billing_cycle)

    def get_amount_normal(self, billing_cycle):
        if self.is_one_off():
            # TODO: This assumes we are asking about the next billing cycle, not the one specified
            is_final_billing_cycle = (self.total_billing_cycles == self.recurrences.count() + 1)

            if is_final_billing_cycle:
                return self.fixed_amount - self.get_billed_amount()
            else:
                splits = ratio_split(
                    amount=self.fixed_amount,
                    ratios=[Decimal('1')] * self.total_billing_cycles,
                )
                #TODO: ...as does this
                return splits[self.recurrences.count()]
        else:
            return self.fixed_amount

    def get_amount_arrears_balance(self, billing_cycle):
        """Get the balance of to_account at the end of billing_cycle"""
        pass

    def get_amount_arrears_transactions(self, billing_cycle):
        """Get the sum of all transaction legs in to_account during given billing cycle"""
        pass

    def get_billed_amount(self):
        """Get the total amount billed so far"""
        return Leg.objects.filter(transaction__recurred_cost__recurring_cost=self).sum_amount()

    @db_transaction.atomic()
    def enact(self, billing_cycle):
        if not self.is_enactable(billing_cycle):
            raise CannotEnactUnenactableRecurringCostError(
                "RecurringCost is unenactable. Disabled: {}, finished: {}, billing complete: {}".format(
                    self.disabled,
                    self._is_finished(),
                    self._is_billing_complete(billing_cycle)
                )
            )

        recurred_cost = RecurredCost(
            recurring_cost=self,
            billing_cycle=billing_cycle,
        )
        recurred_cost.make_transaction()
        recurred_cost.save()

        self.disable_if_done(billing_cycle)

    def disable_if_done(self, billing_cycle, commit=True):
        """Set disabled=True if this cost is done (billing cycles done or billing complete)"""
        if self._is_finished() or self._is_billing_complete(billing_cycle):
            self.disabled = True

        if commit:
            self.save()

    def is_enactable(self, for_billing_cycle):
        return \
            not self.disabled and \
            not self._is_finished() and \
            not self._is_billing_complete(for_billing_cycle)

    def is_one_off(self):
        return bool(self.total_billing_cycles)

    def _is_finished(self):
        """Have the specified number of billing cycles been completed?"""
        if self.is_one_off():
            return self.recurrences.count() >= self.total_billing_cycles
        else:
            return False

    def _is_billing_complete(self, billing_cycle):
        if self.is_one_off():
            return self.get_billed_amount() >= self.get_amount(billing_cycle)
        else:
            return False


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
            ('recurring_cost', 'billing_cycle'),
        )

    def make_transaction(self):
        """Create the transaction for this RecurredCost

        May only be used to create the RecurredCost's initial transaction.

        Returns:
            Transaction: The created transaction, also assigned to self.transaction
        """
        try:
            has_transaction = bool(self.transaction)
        except Transaction.DoesNotExist:
            pass
        else:
            raise CannotRecreateTransactionOnRecurredCost()

        self.transaction = Transaction.objects.create(
            description='Created by recurring cost: {}'.format(self.recurring_cost)
        )
        amount = self.recurring_cost.get_amount(self.billing_cycle)
        splits = self.recurring_cost.splits.all().split(amount)

        self.transaction.legs.add(Leg.objects.create(
            transaction=self.transaction,
            amount=amount,
            account=self.recurring_cost.to_account,
        ))

        for split, split_amount in splits:
            self.transaction.legs.add(Leg.objects.create(
                transaction=self.transaction,
                amount=split_amount * -1,
                account=split.from_account,
            ))

        return self.transaction


