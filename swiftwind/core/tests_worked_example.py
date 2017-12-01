from django.test import TestCase
from django.utils.datetime_safe import datetime, date
from moneyed import Money
from freezegun import freeze_time

from hordak.models.core import Account
from hordak.utilities.currency import Balance
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.core.management.commands import swiftwind_create_accounts
from swiftwind.costs.models import RecurringCost, RecurringCostSplit
from swiftwind.utilities.testing import DataProvider


class WorkedExampleTestCase(DataProvider, TestCase):

    def create_splits(self, recurring_cost):
        RecurringCostSplit.objects.create(recurring_cost=recurring_cost, from_account=self.housemate_account_1)
        RecurringCostSplit.objects.create(recurring_cost=recurring_cost, from_account=self.housemate_account_2)
        RecurringCostSplit.objects.create(recurring_cost=recurring_cost, from_account=self.housemate_account_3)

    def setUp(self):
        # First let's setup our accounts

        # Create standard chart of accounts
        swiftwind_create_accounts.Command().handle(currency='GBP')

        # Create some billing cycles
        BillingCycle._populate(as_of=date(2000, 1, 1))
        self.billing_cycle_1 = BillingCycle.objects.all()[0]
        self.billing_cycle_2 = BillingCycle.objects.all()[1]

        # Pull out some accounts we'll want
        self.bank = Account.objects.get(name='Bank')  # Asset
        self.food = Account.objects.get(name='Food')  # Expense
        self.gas_expense = Account.objects.get(name='Gas Expense')  # Expense
        self.gas_payable = Account.objects.get(name='Gas Payable')  # Liability

        self.housemate_account_1 = self.housemate(account_kwargs=dict(currencies=['GBP'])).account  # Income account
        self.housemate_account_2 = self.housemate(account_kwargs=dict(currencies=['GBP'])).account  # Income account
        self.housemate_account_3 = self.housemate(account_kwargs=dict(currencies=['GBP'])).account  # Income account

        # Recurring cost for food
        self.food_recurring_cost = RecurringCost.objects.create(
            to_account=self.food,
            type=RecurringCost.TYPES.arrears_balance,  # Pay the previous month's balance
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.create_splits(self.food_recurring_cost)

        # Recurring cost for gas
        self.gas_recurring_cost = RecurringCost.objects.create(
            to_account=self.gas_payable,
            fixed_amount=150,
            type=RecurringCost.TYPES.normal,
            initial_billing_cycle=self.billing_cycle_1,
        )
        self.create_splits(self.gas_recurring_cost)

    def test_worked_example(self):
        # Ok, lets go...

        # This is the first billing cycle so let's just enact the recurring costs

        self.food_recurring_cost.enact(self.billing_cycle_1)
        self.gas_recurring_cost.enact(self.billing_cycle_1)

        self.assertEqual(self.bank.balance(), Balance(0, 'GBP'))
        # No food account balance to bill as this is the fist billing cycle
        self.assertEqual(self.food.balance(), Balance(0, 'GBP'))
        self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
        self.assertEqual(self.gas_payable.balance(), Balance(150, 'GBP'))
        self.assertEqual(self.housemate_account_1.balance(), Balance(-50, 'GBP'))
        self.assertEqual(self.housemate_account_2.balance(), Balance(-50, 'GBP'))
        self.assertEqual(self.housemate_account_3.balance(), Balance(-50, 'GBP'))

        # BILLING CYCLE 1

        # Ok, let's spend some money on food
        with freeze_time('2000-01-01'):
            self.bank.transfer_to(self.food, Money(120, 'GBP'))

            self.assertEqual(self.bank.balance(), Balance(-120, 'GBP'))  # changed
            self.assertEqual(self.food.balance(), Balance(120, 'GBP'))  # changed
            self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
            self.assertEqual(self.gas_payable.balance(), Balance(150, 'GBP'))
            self.assertEqual(self.housemate_account_1.balance(), Balance(-50, 'GBP'))
            self.assertEqual(self.housemate_account_2.balance(), Balance(-50, 'GBP'))
            self.assertEqual(self.housemate_account_3.balance(), Balance(-50, 'GBP'))

            # Now, the housemates pay their bills
            self.housemate_account_1.transfer_to(self.bank, amount=Money(50, 'GBP'))
            self.housemate_account_2.transfer_to(self.bank, amount=Money(50, 'GBP'))
            self.housemate_account_3.transfer_to(self.bank, amount=Money(50, 'GBP'))

            self.assertEqual(self.bank.balance(), Balance(30, 'GBP'))  # changed
            self.assertEqual(self.food.balance(), Balance(120, 'GBP'))
            self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
            self.assertEqual(self.gas_payable.balance(), Balance(150, 'GBP'))
            self.assertEqual(self.housemate_account_1.balance(), Balance(0, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_2.balance(), Balance(0, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_3.balance(), Balance(0, 'GBP'))  # changed

        # At the end of billing cycle 1 the housemates have paid their bills and we
        # have the money for gas ready to be paid out when we get a bill

        # BILLING CYCLE 2

        with freeze_time('2000-02-01'):
            # Ok, let's spend some money on food again (a bit more this time)
            self.bank.transfer_to(self.food, Money(180, 'GBP'))
            self.assertEqual(self.bank.balance(), Balance(-150, 'GBP'))  # changed, balance drops as we just spent 180
            self.assertEqual(self.food.balance(), Balance(300, 'GBP'))  # changed, last cycle + this cycle

            # Let's generate the bills again. This time we do get a food bill because
            # we spent some money on food in billing cycle 1
            self.food_recurring_cost.enact(self.billing_cycle_2)
            self.gas_recurring_cost.enact(self.billing_cycle_2)

            self.assertEqual(self.bank.balance(), Balance(-150, 'GBP'))
            # We just moved 120 in from the previous cycle, so 300 -> 180
            self.assertEqual(self.food.balance(), Balance(180, 'GBP'))  # changed
            self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
            self.assertEqual(self.gas_payable.balance(), Balance(300, 'GBP'))
            # Housemate balances: 50 for gas, plus 120/3 (i.e. 40) for food last month
            self.assertEqual(self.housemate_account_1.balance(), Balance(-90, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_2.balance(), Balance(-90, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_3.balance(), Balance(-90, 'GBP'))  # changed

            # Now, the housemates pay their bills
            self.housemate_account_1.transfer_to(self.bank, amount=Money(90, 'GBP'))
            self.housemate_account_2.transfer_to(self.bank, amount=Money(90, 'GBP'))
            self.housemate_account_3.transfer_to(self.bank, amount=Money(90, 'GBP'))

            self.assertEqual(self.bank.balance(), Balance(120, 'GBP'))  # changed (upped by 90*3)
            # this months food spending, will be handled next time around
            self.assertEqual(self.food.balance(), Balance(180, 'GBP'))
            self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
            self.assertEqual(self.gas_payable.balance(), Balance(300, 'GBP'))
            self.assertEqual(self.housemate_account_1.balance(), Balance(0, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_2.balance(), Balance(0, 'GBP'))  # changed
            self.assertEqual(self.housemate_account_3.balance(), Balance(0, 'GBP'))  # changed

            # We also get a gas bill, so lets pay that
            self.bank.transfer_to(self.gas_expense, Money(295, 'GBP'))

            self.assertEqual(self.bank.balance(), Balance(-175, 'GBP'))  # 120 - 295
            self.assertEqual(self.gas_expense.balance(), Balance(295, 'GBP'))

            # ... and use the payable account to clear the expense account
            self.gas_payable.transfer_to(self.gas_expense, Money(295, 'GBP'))

            self.assertEqual(self.bank.balance(), Balance(-175, 'GBP'))  # 120 - 295
            self.assertEqual(self.gas_expense.balance(), Balance(0, 'GBP'))
            self.assertEqual(self.gas_payable.balance(), Balance(5, 'GBP'))
