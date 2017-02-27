from decimal import Decimal

from datetime import date
from django.db.utils import IntegrityError
from django.db import transaction as db_transaction
from django.test import TestCase
from django.test.testcases import TransactionTestCase
from django.urls.base import reverse
from hordak.models import Account
from hordak.tests.utils import DataProvider, BalanceUtils
from hordak.utilities.currency import Balance
from moneyed import Money

from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.costs import tasks
from swiftwind.costs.exceptions import ProvidedBillingCycleBeginsBeforeInitialBillingCycle, \
    CannotEnactUnenactableRecurringCostError, RecurringCostAlreadyEnactedForBillingCycle
from swiftwind.costs.management.commands.enact_costs import Command as EnactCostsCommand
from swiftwind.costs.models import RecurredCost
from .forms import RecurringCostForm
from .models import RecurringCost, RecurringCostSplit


class RecurringCostModelTriggerTestCase(DataProvider, TransactionTestCase):

    # DB constraint tests

    def test_check_recurring_costs_have_splits(self):
        """Any recurring cost must have splits"""
        with self.assertRaises(IntegrityError):
            to_account = self.account(type=Account.TYPES.expense)
            RecurringCost.objects.create(
                to_account=to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01')),
            )

    def test_check_cannot_create_recurred_cost_for_disabled_cost(self):
        """Cannot created RecurredCosts for disabled RecurringCosts"""
        to_account = self.account(type=Account.TYPES.expense)
        billing_cycle = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))
        billing_cycle.refresh_from_db()

        with db_transaction.atomic():
            # Create the cost and splits
            recurring_cost = RecurringCost.objects.create(
                to_account=to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=None,
                disabled=True,
            )
            split = RecurringCostSplit.objects.create(
                recurring_cost=recurring_cost,
                from_account=self.account(type=Account.TYPES.income),
                portion=Decimal('1'),
            )
            recurring_cost.splits.add(split)

        recurring_cost.refresh_from_db()
        with db_transaction.atomic():
            # Create the RecurredCost & transactions
            recurred_cost = RecurredCost(
                recurring_cost=recurring_cost,
                billing_cycle=billing_cycle,
            )
            recurred_cost.make_transaction()

        with self.assertRaises(IntegrityError):
            recurred_cost.save()

    def test_check_recurring_cost_cannot_be_disabled_with_initial_transaction_id(self):
        """RecurringCost cannot be disabled AND have an initial_transaction

        We want to make sure initial_billing_cycle is set to something if cost is ever un-disabled
        """

        with db_transaction.atomic():
            to_account = self.account(type=Account.TYPES.expense)
            billing_cycle = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))

            recurring_cost = RecurringCost.objects.create(
                to_account=to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=billing_cycle,
            )
            split = RecurringCostSplit.objects.create(
                recurring_cost=recurring_cost,
                from_account=self.account(type=Account.TYPES.income),
                portion=Decimal('1'),
            )
            recurring_cost.splits.add(split)

        with self.assertRaises(IntegrityError):
            recurring_cost.initial_billing_cycle = billing_cycle
            recurring_cost.disabled = True
            recurring_cost.save()

        with self.assertRaises(IntegrityError):
            recurring_cost.initial_billing_cycle = None
            recurring_cost.disabled = False
            recurring_cost.save()

        # OK
        recurring_cost.initial_billing_cycle = None
        recurring_cost.disabled = True
        recurring_cost.save()

        # OK
        recurring_cost.initial_billing_cycle = billing_cycle
        recurring_cost.disabled = False
        recurring_cost.save()

    def test_check_fixed_amount_requires_type_normal(self):
        """Only RecurringCosts with type=normal can have a fixed_amount set

        Other types of RecurringCost will always read their amount from an Account
        """

        with db_transaction.atomic():
            to_account = self.account(type=Account.TYPES.expense)
            billing_cycle = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))

            recurring_cost = RecurringCost.objects.create(
                to_account=to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=billing_cycle,
            )
            split = RecurringCostSplit.objects.create(
                recurring_cost=recurring_cost,
                from_account=self.account(type=Account.TYPES.income),
                portion=Decimal('1'),
            )
            recurring_cost.splits.add(split)

        with self.assertRaises(IntegrityError):
            recurring_cost.type = RecurringCost.TYPES.normal
            recurring_cost.fixed_amount = None
            recurring_cost.save()

        with self.assertRaises(IntegrityError):
            recurring_cost.type = RecurringCost.TYPES.arrears_balance
            recurring_cost.fixed_amount = 100
            recurring_cost.save()

        # OK
        recurring_cost.type = RecurringCost.TYPES.normal
        recurring_cost.fixed_amount = 100
        recurring_cost.save()

        # OK
        recurring_cost.type = RecurringCost.TYPES.arrears_balance
        recurring_cost.fixed_amount = None
        recurring_cost.save()


class RecurringCostModelTestCase(DataProvider, BalanceUtils, TestCase):

    def setUp(self):
        self.bank = self.account(type=Account.TYPES.asset)
        self.to_account = self.account(type=Account.TYPES.expense)
        self.billing_cycle_1 = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))
        self.billing_cycle_2 = BillingCycle.objects.create(date_range=('2000-02-01', '2000-03-01'))
        self.billing_cycle_3 = BillingCycle.objects.create(date_range=('2000-03-01', '2000-04-01'))
        self.billing_cycle_4 = BillingCycle.objects.create(date_range=('2000-04-01', '2000-05-01'))

        self.billing_cycle_1.refresh_from_db()
        self.billing_cycle_2.refresh_from_db()
        self.billing_cycle_3.refresh_from_db()
        self.billing_cycle_4.refresh_from_db()

    def add_split(self, recurring_cost):
        # Required by database constraint, but not relevant to most of the tests.
        # We therefore use this utility method to create this where required.
        split = RecurringCostSplit.objects.create(
            recurring_cost=recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion=Decimal('1'),
        )
        recurring_cost.splits.add(split)
        return split

    # Test get_amount()

    def test_recurring_normal_get_amount(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)

        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 100)

    def test_recurring_arrears_balance_get_amount(self):
        self.bank.transfer_to(self.to_account, Money(100, 'EUR'), date='2000-01-15')
        self.bank.transfer_to(self.to_account, Money(50, 'EUR'), date='2000-02-15')
        self.bank.transfer_to(self.to_account, Money(10, 'EUR'), date='2000-03-01')

        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            type=RecurringCost.TYPES.arrears_balance,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_2), 150)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_3), 160)

    def test_recurring_arrears_transactions_get_amount(self):
        self.bank.transfer_to(self.to_account, Money(100, 'EUR'), date='2000-01-01')
        self.bank.transfer_to(self.to_account, Money(20, 'EUR'), date='2000-01-31')
        self.bank.transfer_to(self.to_account, Money(50, 'EUR'), date='2000-02-15')
        self.bank.transfer_to(self.to_account, Money(10, 'EUR'), date='2000-03-15')

        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            type=RecurringCost.TYPES.arrears_transactions,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_1), 120)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_2), 50)
        self.assertBalanceEqual(recurring_cost.get_amount(self.billing_cycle_3), 10)

    def test_one_off_normal_get_amount(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
            total_billing_cycles=3,  # Makes this a one-off cost
        )
        self.add_split(recurring_cost)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), Decimal('33.33'))
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), Decimal('33.33'))
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), Decimal('33.34'))
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_4), Decimal('0'))

    def test_one_off_arrears_balance_get_amount(self):
        """type=arrears_balance cannot have arrears_transactions set"""
        with self.assertRaises(IntegrityError):
            RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.arrears_balance,
                total_billing_cycles=2,
            )

    def test_one_off_arrears_transactions_get_amount(self):
        """type=arrears_transactions cannot have arrears_transactions set"""
        with self.assertRaises(IntegrityError):
            RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.arrears_transactions,
                total_billing_cycles=2,
            )

    # Test boolean methods

    def test_is_one_off_true(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
            total_billing_cycles=2,
        )
        self.add_split(recurring_cost)
        self.assertTrue(recurring_cost.is_one_off())

    def test_is_one_off_false(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)
        self.assertFalse(recurring_cost.is_one_off())

    def test_is_finished(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
            total_billing_cycles=2,  # _is_finished only apples to one-off costs
        )
        self.add_split(recurring_cost)

        self.assertFalse(recurring_cost._is_finished(date(1999, 1, 1)))  # before initial cycle

        self.assertFalse(recurring_cost._is_finished(date(2000, 1, 1)))   # first day of first cycle
        self.assertFalse(recurring_cost._is_finished(date(2000, 2, 29)))  # last day of second cycle (2000 is leap year)

        self.assertTrue(recurring_cost._is_finished(date(2000, 3, 1)))  # First day of third cycle = False
        self.assertTrue(recurring_cost._is_finished(date(2010, 1, 1)))  # 10 years in the future still False

    def test_is_enactable_one_off_finishes(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
            total_billing_cycles=2,  # Two cycles only!
        )
        self.add_split(recurring_cost)

        # Additional testing in test_is_finished()
        self.assertTrue(recurring_cost.is_enactable(date(2000, 1, 1)))   # first day of first cycle
        self.assertFalse(recurring_cost.is_enactable(date(2010, 1, 1)))  # 10 years in the future still False

    def test_is_enactable_false_because_disabled(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=None,
            disabled=True,
        )
        self.add_split(recurring_cost)
        self.assertFalse(recurring_cost.is_enactable(date(2000, 1, 1)))

    # Test _get_billing_cycle_number()

    def test_get_billing_cycle_number(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)
        self.assertEqual(recurring_cost._get_billing_cycle_number(self.billing_cycle_1), 1)
        self.assertEqual(recurring_cost._get_billing_cycle_number(self.billing_cycle_2), 2)
        self.assertEqual(recurring_cost._get_billing_cycle_number(self.billing_cycle_3), 3)
        self.assertEqual(recurring_cost._get_billing_cycle_number(self.billing_cycle_4), 4)

    def test_get_billing_cycle_number_error(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_2,
        )
        self.add_split(recurring_cost)

        with self.assertRaises(ProvidedBillingCycleBeginsBeforeInitialBillingCycle):
            recurring_cost._get_billing_cycle_number(self.billing_cycle_1)

        self.assertEqual(recurring_cost._get_billing_cycle_number(self.billing_cycle_2), 1)

    # Misc

    def test_get_billed_amount(self):
        """get_billed_amount() show how much has been billed so far"""
        from_account = self.account(type=Account.TYPES.expense)
        transaction = from_account.transfer_to(self.to_account, Money(100, 'EUR'))

        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.add_split(recurring_cost)
        recurring_cost.save()
        recurred_cost = RecurredCost.objects.create(
            recurring_cost=recurring_cost,
            billing_cycle=self.billing_cycle_1,
            transaction=transaction,
        )
        recurred_cost.save()
        self.assertEqual(recurring_cost.get_billed_amount(), Balance(100, 'EUR'))


class RecurringCostModelTransactionTestCase(DataProvider, BalanceUtils, TransactionTestCase):
    # Test the enact() method which requires transactions

    def setUp(self):
        self.login()

        self.bank = self.account(type=Account.TYPES.asset)
        self.to_account = self.account(type=Account.TYPES.expense)
        self.billing_cycle_1 = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))
        self.billing_cycle_2 = BillingCycle.objects.create(date_range=('2000-02-01', '2000-03-01'))
        self.billing_cycle_3 = BillingCycle.objects.create(date_range=('2000-03-01', '2000-04-01'))
        self.billing_cycle_4 = BillingCycle.objects.create(date_range=('2000-04-01', '2000-05-01'))

        self.billing_cycle_1.refresh_from_db()
        self.billing_cycle_2.refresh_from_db()
        self.billing_cycle_3.refresh_from_db()
        self.billing_cycle_4.refresh_from_db()

    def add_split(self, recurring_cost):
        # Required by database constraint, but not relevant to most of the tests.
        # We therefore use this utility method to create this where required.
        split = RecurringCostSplit.objects.create(
            recurring_cost=recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion=Decimal('1'),
        )
        recurring_cost.splits.add(split)
        return split

    def test_recurring_enact(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        recurring_cost.enact(self.billing_cycle_1)
        self.assertBalanceEqual(self.to_account.balance(), 100)  # 100 every month
        self.assertBalanceEqual(split1.from_account.balance(), 50)
        self.assertBalanceEqual(split2.from_account.balance(), 50)

        recurring_cost.enact(self.billing_cycle_2)
        self.assertBalanceEqual(self.to_account.balance(), 200)
        self.assertBalanceEqual(split1.from_account.balance(), 100)
        self.assertBalanceEqual(split2.from_account.balance(), 100)

    def test_one_off_enact(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
                total_billing_cycles=2,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        recurring_cost.enact(self.billing_cycle_1)
        self.assertBalanceEqual(self.to_account.balance(), 50)  # 100 spread across 2 months
        self.assertBalanceEqual(split1.from_account.balance(), 25)
        self.assertBalanceEqual(split2.from_account.balance(), 25)

        recurring_cost.enact(self.billing_cycle_2)
        self.assertBalanceEqual(self.to_account.balance(), 100)
        self.assertBalanceEqual(split1.from_account.balance(), 50)
        self.assertBalanceEqual(split2.from_account.balance(), 50)

        with self.assertRaises(CannotEnactUnenactableRecurringCostError):
            recurring_cost.enact(self.billing_cycle_3)

    def test_enact_twice_same_billing_period_error(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        recurring_cost.enact(self.billing_cycle_1)
        with self.assertRaises(RecurringCostAlreadyEnactedForBillingCycle):
            recurring_cost.enact(self.billing_cycle_1)

    # Misc other tests that use enact()

    def test_is_billing_complete(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
                total_billing_cycles=2,  # _is_billing_complete only apples to one-off costs
            )
            self.add_split(recurring_cost)

        self.assertFalse(recurring_cost._is_billing_complete())
        recurring_cost.enact(self.billing_cycle_1)
        self.assertFalse(recurring_cost._is_billing_complete())
        recurring_cost.enact(self.billing_cycle_2)
        self.assertTrue(recurring_cost._is_billing_complete())

    def test_disabled_when_done(self):
        """Test that one-off costs are disabled when their last billing cycle is enacted"""
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
                total_billing_cycles=2,
            )
            self.add_split(recurring_cost)

        self.assertFalse(recurring_cost.disabled)
        recurring_cost.enact(self.billing_cycle_1)
        self.assertFalse(recurring_cost.disabled)
        recurring_cost.enact(self.billing_cycle_2)
        self.assertTrue(recurring_cost.disabled)

    def test_enact_costs_manager(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        RecurringCost.objects.enact(as_of=date(2000, 2, 5))

        self.assertBalanceEqual(self.to_account.balance(), 200)
        self.assertBalanceEqual(split1.from_account.balance(), 100)
        self.assertBalanceEqual(split2.from_account.balance(), 100)

    def test_enact_costs_task(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        tasks.enact_costs(as_of=date(2000, 2, 5))

        self.assertBalanceEqual(self.to_account.balance(), 200)
        self.assertBalanceEqual(split1.from_account.balance(), 100)
        self.assertBalanceEqual(split2.from_account.balance(), 100)

    def test_enact_costs_command_with_as_of(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        EnactCostsCommand().handle(as_of='2000-02-05')

        self.assertBalanceEqual(self.to_account.balance(), 200)
        self.assertBalanceEqual(split1.from_account.balance(), 100)
        self.assertBalanceEqual(split2.from_account.balance(), 100)

    def test_enact_costs_command_default_as_of(self):
        with db_transaction.atomic():
            recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle_1,
            )
            split1 = self.add_split(recurring_cost)
            split2 = self.add_split(recurring_cost)

        EnactCostsCommand().handle()

        # Uses today's date, so all billing cycles are enacted. Therefore larger balances
        self.assertBalanceEqual(self.to_account.balance(), 400)
        self.assertBalanceEqual(split1.from_account.balance(), 200)
        self.assertBalanceEqual(split2.from_account.balance(), 200)


class RecurringCostSplitModelTestCase(DataProvider, TestCase):

    def setUp(self):
        to_account = self.account(type=Account.TYPES.expense)
        self.recurring_cost = RecurringCost.objects.create(
            to_account=to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=BillingCycle.objects.create(date_range=('2016-01-01', '2016-02-01'))
        )
        self.split1 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='1.00'
        )
        self.split2 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='0.50'
        )
        self.split3 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='0.50'
        )

    def test_queryset_split(self):
        splits = self.recurring_cost.splits.all().split(100)
        objs_dict = {obj: amount for obj, amount in splits}

        self.assertEqual(objs_dict[self.split1], 50)
        self.assertEqual(objs_dict[self.split2], 25)
        self.assertEqual(objs_dict[self.split3], 25)


class RecurredCostModelTestCase(DataProvider, TestCase):

    def setUp(self):
        self.billing_cycle = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))
        to_account = self.account(type=Account.TYPES.expense)

        self.recurring_cost = RecurringCost.objects.create(
            to_account=to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle,
        )
        self.split1 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='1.00'
        )
        self.split2 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='0.50'
        )
        self.split3 = RecurringCostSplit.objects.create(
            recurring_cost=self.recurring_cost,
            from_account=self.account(type=Account.TYPES.income),
            portion='0.50'
        )

        self.recurring_cost.refresh_from_db()

        # Note that we don't save this
        self.recurred_cost = RecurredCost(
            recurring_cost=self.recurring_cost,
            billing_cycle=self.billing_cycle,
        )

    def test_make_transaction(self):
        self.recurred_cost.make_transaction()
        self.recurred_cost.save()

        transaction = self.recurred_cost.transaction
        self.assertEqual(transaction.legs.count(), 4)  # 3 splits (from accounts) + 1 to account


class RecurringCostFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.expense_account = self.account(type=Account.TYPES.expense)
        self.housemate_parent_account = self.account(name='Housemate Income', type=Account.TYPES.income)
        self.housemate_1 = self.account(parent=self.housemate_parent_account)
        self.housemate_2 = self.account(parent=self.housemate_parent_account)
        self.housemate_3 = self.account(parent=self.housemate_parent_account)

        BillingCycle.populate()
        self.first_billing_cycle = BillingCycle.objects.first()

    def test_valid(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.normal,
            disabled='',
            fixed_amount='100',
            initial_billing_cycle=self.first_billing_cycle.pk,
        ))
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        obj.refresh_from_db()
        self.assertEqual(obj.to_account, self.expense_account)
        self.assertEqual(obj.type, RecurringCost.TYPES.normal)
        self.assertEqual(obj.disabled, False)
        self.assertEqual(obj.fixed_amount, Decimal('100'))
        self.assertEqual(obj.initial_billing_cycle, self.first_billing_cycle)

        splits = obj.splits.all()
        self.assertEqual(splits.count(), 3)

        split_1 = obj.splits.get(from_account=self.housemate_1)
        split_2 = obj.splits.get(from_account=self.housemate_2)
        split_3 = obj.splits.get(from_account=self.housemate_3)

        self.assertEqual(split_1.portion, 1)
        self.assertEqual(split_2.portion, 1)
        self.assertEqual(split_3.portion, 1)

    def test_fixed_amount_not_allowed(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.arrears_balance,
            disabled='',
            fixed_amount='100',
            total_billing_cycles='5',
            initial_billing_cycle=self.first_billing_cycle.pk,
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('fixed_amount', form.errors)

    def test_fixed_amount_disabled(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.normal,
            disabled='on',
            fixed_amount='100',
            total_billing_cycles='5',
            initial_billing_cycle=None,
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_initial_billing_cycle_required(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.normal,
            disabled='',
            fixed_amount='100',
            total_billing_cycles='5',
            initial_billing_cycle=None,
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('initial_billing_cycle', form.errors)

    def test_initial_billing_cycle_unrequired(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.normal,
            disabled='on    ',
            fixed_amount='100',
            total_billing_cycles='5',
            initial_billing_cycle=self.first_billing_cycle,
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('initial_billing_cycle', form.errors)


class RecurringCostsViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.login()

        BillingCycle.populate()
        self.first_billing_cycle = BillingCycle.objects.first()

        self.expense_account = self.account(type=Account.TYPES.expense)
        self.housemate_parent_account = self.account(name='Housemate Income', type=Account.TYPES.income)
        self.housemate_1 = self.account(parent=self.housemate_parent_account)
        self.housemate_2 = self.account(parent=self.housemate_parent_account)
        self.housemate_3 = self.account(parent=self.housemate_parent_account)

        with db_transaction.atomic():
            self.recurring_cost_1 = RecurringCost.objects.create(to_account=self.expense_account, fixed_amount=100, initial_billing_cycle=self.first_billing_cycle)
            self.split1 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_1)
            self.split2 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_2)
            self.split3 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_3)

        self.view_url = reverse('costs:recurring')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('formset', context)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,

            'form-0-id': self.recurring_cost_1.id,
            'form-0-to_account': self.expense_account.uuid,
            'form-0-type': RecurringCost.TYPES.normal,
            'form-0-fixed_amount': '200',
            'form-0-disabled': '',
            'form-0-initial_billing_cycle': self.first_billing_cycle.pk,
            'form-0-splits-TOTAL_FORMS': 3,
            'form-0-splits-INITIAL_FORMS': 3,
            'form-0-splits-0-id': self.split1.id,
            'form-0-splits-0-portion': 2.00,
            'form-0-splits-1-id': self.split2.id,
            'form-0-splits-1-portion': 3.00,
            'form-0-splits-2-id': self.split3.id,
            'form-0-splits-2-portion': 4.00,
        })
        context = response.context
        if response.context:
            self.assertFalse(context['formset'].errors)

        self.recurring_cost_1.refresh_from_db()
        self.assertEqual(self.recurring_cost_1.fixed_amount, 200)

        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()

        self.assertEqual(self.split1.portion, 2)
        self.assertEqual(self.split2.portion, 3)
        self.assertEqual(self.split3.portion, 4)


class CreateRecurringCostViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.login()

        BillingCycle.populate()
        self.billing_cycle = BillingCycle.objects.first()

        self.expense_account = self.account(type=Account.TYPES.expense)
        self.housemate_parent_account = self.account(name='Housemate Income', type=Account.TYPES.income)
        self.housemate_1 = self.account(parent=self.housemate_parent_account)
        self.housemate_2 = self.account(parent=self.housemate_parent_account)
        self.housemate_3 = self.account(parent=self.housemate_parent_account)

        self.view_url = reverse('costs:create_recurring')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('form', context)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'to_account': self.expense_account.uuid,
            'fixed_amount': Decimal('200'),
            'disabled': '',
            'type': RecurringCost.TYPES.normal,
            'initial_billing_cycle': self.billing_cycle.pk,
        })
        context = response.context
        if response.context:
            self.assertFalse(context['form'].errors)

        self.assertEqual(RecurringCost.objects.count(), 1)
        recurring_cost = RecurringCost.objects.get()
        self.assertEqual(recurring_cost.to_account, self.expense_account)
        self.assertEqual(recurring_cost.total_billing_cycles, None)
        self.assertEqual(recurring_cost.fixed_amount, 200)
        self.assertEqual(recurring_cost.disabled, False)

        self.assertEqual(recurring_cost.splits.count(), 3)


class OneOffCostsViewTestCase(DataProvider, TransactionTestCase):

    def setUp(self):
        self.login()

        BillingCycle.populate()
        self.billing_cycle = BillingCycle.objects.first()

        self.expense_account = self.account(type=Account.TYPES.expense)
        self.housemate_parent_account = self.account(name='Housemate Income', type=Account.TYPES.income)
        self.housemate_1 = self.account(parent=self.housemate_parent_account)
        self.housemate_2 = self.account(parent=self.housemate_parent_account)
        self.housemate_3 = self.account(parent=self.housemate_parent_account)

        with db_transaction.atomic():
            self.recurring_cost_1 = RecurringCost.objects.create(to_account=self.expense_account, fixed_amount=100,
                                                                 total_billing_cycles=2, initial_billing_cycle=self.billing_cycle)
            self.split1 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_1)
            self.split2 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_2)
            self.split3 = RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_3)

        self.view_url = reverse('costs:one_off')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('formset', context)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'form-TOTAL_FORMS': 1,
            'form-INITIAL_FORMS': 1,

            'form-0-id': self.recurring_cost_1.id,
            'form-0-to_account': self.expense_account.uuid,
            'form-0-total_billing_cycles': 3,
            'form-0-fixed_amount': Decimal('200'),
            'form-0-initial_billing_cycle': self.billing_cycle.pk,
            'form-0-disabled': '',
            'form-0-splits-TOTAL_FORMS': 3,
            'form-0-splits-INITIAL_FORMS': 3,
            'form-0-splits-0-id': self.split1.id,
            'form-0-splits-0-portion': 2.00,
            'form-0-splits-1-id': self.split2.id,
            'form-0-splits-1-portion': 3.00,
            'form-0-splits-2-id': self.split3.id,
            'form-0-splits-2-portion': 4.00,
        })
        context = response.context
        if response.context:
            self.assertFalse(context['formset'].errors)

        self.recurring_cost_1.refresh_from_db()
        self.assertEqual(self.recurring_cost_1.total_billing_cycles, 3)
        self.assertEqual(self.recurring_cost_1.fixed_amount, 200)

        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()

        self.assertEqual(self.split1.portion, 2)
        self.assertEqual(self.split2.portion, 3)
        self.assertEqual(self.split3.portion, 4)


class CreateOneOffCostViewTestCase(DataProvider, TransactionTestCase):

    def setUp(self):
        self.login()

        BillingCycle.populate()
        self.billing_cycle = BillingCycle.objects.first()

        self.expense_account = self.account(type=Account.TYPES.expense)
        self.housemate_parent_account = self.account(name='Housemate Income', type=Account.TYPES.income)
        self.housemate_1 = self.account(parent=self.housemate_parent_account)
        self.housemate_2 = self.account(parent=self.housemate_parent_account)
        self.housemate_3 = self.account(parent=self.housemate_parent_account)

        self.view_url = reverse('costs:create_one_off')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('form', context)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'to_account': self.expense_account.uuid,
            'fixed_amount': Decimal('200'),
            'total_billing_cycles': 2,
            'initial_billing_cycle': self.billing_cycle.pk,
        })
        context = response.context
        if response.context:
            self.assertFalse(context['form'].errors)

        self.assertEqual(RecurringCost.objects.count(), 1)
        recurring_cost = RecurringCost.objects.get()
        self.assertEqual(recurring_cost.to_account, self.expense_account)
        self.assertEqual(recurring_cost.total_billing_cycles, 2)
        self.assertEqual(recurring_cost.fixed_amount, 200)
        self.assertEqual(recurring_cost.disabled, False)
        self.assertEqual(recurring_cost.initial_billing_cycle, self.billing_cycle)

        self.assertEqual(recurring_cost.splits.count(), 3)

    def test_post_invalid_missing_total_billing_cycles(self):
        response = self.client.post(self.view_url, data={
            'to_account': self.expense_account.uuid,
            'fixed_amount': Decimal('200'),
            'total_billing_cycles': '',
        })
        form = response.context['form']
        self.assertFalse(form.is_valid())

    def test_post_invalid_missing_fixed_amount(self):
        response = self.client.post(self.view_url, data={
            'to_account': self.expense_account.uuid,
            'fixed_amount': '',
            'total_billing_cycles': '3',
        })
        form = response.context['form']
        self.assertFalse(form.is_valid())

    def test_post_invalid_missing_to_account(self):
        response = self.client.post(self.view_url, data={
            'to_account': '',
            'fixed_amount': Decimal('200'),
            'total_billing_cycles': '3',
        })
        form = response.context['form']
        self.assertFalse(form.is_valid())



