import six
import tablib
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.datetime_safe import date
from hordak.models import Account, Transaction, StatementLine, StatementImport
from django.test import TestCase
from django.test import Client

from swiftwind.transactions.models import TransactionImportColumn
from swiftwind.transactions.resources import StatementLineResource
from .forms import SimpleTransactionForm, TransactionImportForm
from .models import TransactionImport


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
        from_leg = transaction.legs.get(account=self.from_account)
        to_leg = transaction.legs.get(account=self.to_account)

        self.assertEqual(from_leg.amount, -50)
        self.assertEqual(to_leg.amount, 50)


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


class CreateImportViewTestCase(TestCase):

    def setUp(self):
        self.view_url = reverse('transactions:import_create')

    def test_load(self):
        c = Client()
        response = c.post(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_success_url(self):
        from swiftwind.transactions.views import CreateImportView
        view = CreateImportView()
        view.object = TransactionImport.objects.create()
        self.assertIn(str(view.object.uuid), view.get_success_url())

class TransactionFormTestCase(TestCase):

    def setUp(self):
        self.f = SimpleUploadedFile('data.csv',
                                    six.binary_type('Number,Date,Account,Amount,Subcategory,Memo', encoding='utf8'))

    def test_create(self):
        form = TransactionImportForm(files=dict(file=self.f))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        obj = TransactionImport.objects.get()
        self.assertEqual(obj.columns.count(), 6)

    def test_edit(self):
        obj = TransactionImport.objects.create(has_headings=True, file=self.f)
        form = TransactionImportForm(files=dict(file=self.f), instance=obj)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(obj.columns.count(), 0)


class SetupImportViewTestCase(TestCase):

    def setUp(self):
        self.transaction_import = TransactionImport.objects.create()
        self.view_url = reverse('transactions:import_setup', args=[self.transaction_import.uuid])

    def test_load(self):
        c = Client()
        response = c.get(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_submit(self):
        c = Client()
        column1 = TransactionImportColumn.objects.create(
            transaction_import=self.transaction_import,
            column_number=1,
            column_heading='Transaction Date',
            example='1/1/1'
        )

        column2 = TransactionImportColumn.objects.create(
            transaction_import=self.transaction_import,
            column_number=2,
            column_heading='Transaction Amount',
            example='123.45'
        )

        response = c.post(self.view_url, data={
            'date_format': '%d-%m-%Y',

            'columns-INITIAL_FORMS': '2',
            'columns-TOTAL_FORMS': '2',

            'columns-0-id': column1.pk,
            'columns-0-to_field': 'date',

            'columns-1-id': column2.pk,
            'columns-1-to_field': 'amount',
        })
        if response.context:
            # If we have a context then it is going to be because the form has errors
            self.assertFalse(response.context['form'].errors)

        self.transaction_import.refresh_from_db()
        column1.refresh_from_db()
        column2.refresh_from_db()

        self.assertEqual(self.transaction_import.date_format, '%d-%m-%Y')
        self.assertEqual(column1.to_field, 'date')
        self.assertEqual(column2.to_field, 'amount')



class TransactionImportTestCase(TestCase):

    def test_create_columns_ok(self):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   '1,1/1/1,123456789,123,OTH,Some random notes',
                                   encoding='utf8')
                               )

        inst = TransactionImport.objects.create(has_headings=True, file=f)
        inst.create_columns()

        columns = inst.columns.all()

        self.assertEqual(columns[0].column_number, 1)
        self.assertEqual(columns[0].column_heading, 'Number')
        self.assertEqual(columns[0].example, '1')

        self.assertEqual(columns[1].column_number, 2)
        self.assertEqual(columns[1].column_heading, 'Date')
        self.assertEqual(columns[1].example, '1/1/1')

        self.assertEqual(columns[2].column_number, 3)
        self.assertEqual(columns[2].column_heading, 'Account')
        self.assertEqual(columns[2].example, '123456789')

        self.assertEqual(columns[3].column_number, 4)
        self.assertEqual(columns[3].column_heading, 'Amount')
        self.assertEqual(columns[3].example, '123')

        self.assertEqual(columns[4].column_number, 5)
        self.assertEqual(columns[4].column_heading, 'Subcategory')
        self.assertEqual(columns[4].example, 'OTH')

        self.assertEqual(columns[5].column_number, 6)
        self.assertEqual(columns[5].column_heading, 'Memo')
        self.assertEqual(columns[5].example, 'Some random notes')


class StatementLineResourceTestCase(TestCase):
    """Test the resource definition in resources.py"""

    def setUp(self):
        self.account = Account.objects.create(name='Bank', code='1')

    def makeResource(self):
        statement_import = StatementImport.objects.create(bank_account=self.account)
        return StatementLineResource(statement_import)

    def test_import_one(self):
        dataset = tablib.Dataset(
            [date(2016, 6, 15), '5.10', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 1)
        obj = StatementLine.objects.get()
        self.assertEqual(obj.date, date(2016, 6, 15))
        self.assertEqual(obj.amount, Decimal('5.10'))
        self.assertEqual(obj.description, 'Example payment')

    def test_import_skip_duplicates(self):
        dataset = tablib.Dataset(
            [date(2016, 6, 15), '5.10', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)
        # Now do the import again
        self.makeResource().import_data(dataset)

        # The record in the second should have been ignored
        self.assertEqual(StatementLine.objects.count(), 1)


    def test_import_two_identical(self):
        """Ensure they both get imported and that one doesnt get skipped as a duplicate

        After all, if there are two imported rows that look identical, it is probably because
        there are two identical transactions.
        """
        dataset = tablib.Dataset(
            [date(2016, 6, 15), '5.10', 'Example payment'],
            [date(2016, 6, 15), '5.10', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 2)
