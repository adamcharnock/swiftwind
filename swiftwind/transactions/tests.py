from hordak.models import Account, Transaction
from django.test import TestCase

from .forms import SimpleTransactionForm


class SimpleTransactionFormTestCase(TestCase):

    def setUp(self):
        self.from_account = Account.objects.create(name='From Account', type=Account.TYPES.income, code='1')
        self.to_account = Account.objects.create(name='To Account', type=Account.TYPES.income, code='2')

        self.bank = Account.objects.create(name='Bank', type=Account.TYPES.asset, code='5')
        self.income = Account.objects.create(name='Income', type=Account.TYPES.income, code='6')
        self.expense = Account.objects.create(name='Expense', type=Account.TYPES.expense, code='7')

    def test_valid_data(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount='50.00',
        ))
        self.assertTrue(form.is_valid())
        form.save()

        # Transaction exists with two legs
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'A test simple transaction')
        self.assertEqual(transaction.legs.count(), 2)

        # Account balances changed
        self.assertEqual(self.from_account.balance(), -50)
        self.assertEqual(self.to_account.balance(), 50)

        # Check transaction legs have amounts set as expected
        credit = transaction.legs.debits()[0]
        debit = transaction.legs.credits()[0]

        self.assertEqual(credit.account, self.from_account)
        self.assertEqual(credit.amount, 50)

        self.assertEqual(debit.account, self.to_account)
        self.assertEqual(debit.amount, -50)

    def test_transfer_from_bank_to_income(self):
        """If we move money out of the bank and into an income account, we expect both values to go up"""

        form = SimpleTransactionForm(dict(
            from_account=self.bank.uuid,
            to_account=self.income.uuid,
            description='A test simple transaction',
            amount='50.00',
        ))
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(self.bank.balance(), 50)
        self.assertEqual(self.income.balance(), 50)

    def test_no_from_account(self):
        form = SimpleTransactionForm(dict(
            from_account='',
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount='50.00',
        ))
        self.assertFalse(form.is_valid())

    def test_no_to_account(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account='',
            description='A test simple transaction',
            amount='50.00',
        ))
        self.assertFalse(form.is_valid())

    def test_no_description_account(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='',
            amount='50.00',
        ))
        self.assertTrue(form.is_valid())  # valid

    def test_no_amount(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount='',
        ))
        self.assertFalse(form.is_valid())
