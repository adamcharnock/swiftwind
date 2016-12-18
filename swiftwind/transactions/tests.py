import logging
from decimal import Decimal

import six
import tablib
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils.datetime_safe import date
from hordak.models import Account, StatementLine, StatementImport

from swiftwind.transactions.forms import TransactionImportForm
from swiftwind.transactions.models import TransactionImportColumn
from swiftwind.transactions.resources import StatementLineResource
from swiftwind.utilities.testing import DataProvider
from .models import TransactionImport


class CreateImportViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.view_url = reverse('transactions:import_create')

    def test_load(self):
        c = Client()
        response = c.post(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_success_url(self):
        from swiftwind.transactions.views import CreateImportView
        view = CreateImportView()
        view.object = TransactionImport.objects.create(hordak_import=self.statement_import())
        self.assertIn(str(view.object.uuid), view.get_success_url())


class SetupImportViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.transaction_import = TransactionImport.objects.create(hordak_import=self.statement_import())
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


class TransactionImportTestCase(DataProvider, TestCase):

    def test_create_columns_ok(self):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/1,123456789,123,OTH,Some random notes')
                               )

        inst = TransactionImport.objects.create(has_headings=True, file=f, hordak_import=self.statement_import())
        inst.create_columns()

        columns = inst.columns.all()

        self.assertEqual(columns[0].column_number, 1)
        self.assertEqual(columns[0].column_heading, 'Number')
        self.assertEqual(columns[0].to_field, None)
        self.assertEqual(columns[0].example, '1')

        self.assertEqual(columns[1].column_number, 2)
        self.assertEqual(columns[1].column_heading, 'Date')
        self.assertEqual(columns[1].to_field, 'date')
        self.assertEqual(columns[1].example, '1/1/1')

        self.assertEqual(columns[2].column_number, 3)
        self.assertEqual(columns[2].column_heading, 'Account')
        self.assertEqual(columns[2].to_field, None)
        self.assertEqual(columns[2].example, '123456789')

        self.assertEqual(columns[3].column_number, 4)
        self.assertEqual(columns[3].column_heading, 'Amount')
        self.assertEqual(columns[3].to_field, 'amount')
        self.assertEqual(columns[3].example, '123')

        self.assertEqual(columns[4].column_number, 5)
        self.assertEqual(columns[4].column_heading, 'Subcategory')
        self.assertEqual(columns[4].to_field, None)
        self.assertEqual(columns[4].example, 'OTH')

        self.assertEqual(columns[5].column_number, 6)
        self.assertEqual(columns[5].column_heading, 'Memo')
        self.assertEqual(columns[5].to_field, 'description')
        self.assertEqual(columns[5].example, 'Some random notes')


class StatementLineResourceTestCase(DataProvider, TestCase):
    """Test the resource definition in resources.py"""

    def setUp(self):
        self.account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.INFO)

    def makeResource(self):
        statement_import = StatementImport.objects.create(bank_account=self.account)
        return StatementLineResource('%d/%m/%Y', statement_import)

    def test_import_one(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '5.10', 'Example payment'],
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
            ['15/6/2016', '5.10', 'Example payment'],
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
            ['15/6/2016', '5.10', 'Example payment'],
            ['15/6/2016', '5.10', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 2)

    def test_import_a_few(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '5.10', 'Example payment'],
            ['16/6/2016', '10.91', 'Another payment'],
            ['17/6/2016', '-1.23', 'Paying someone'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 3)
        objs = StatementLine.objects.all().order_by('pk')

        self.assertEqual(objs[0].date, date(2016, 6, 15))
        self.assertEqual(objs[0].amount, Decimal('5.10'))
        self.assertEqual(objs[0].description, 'Example payment')

        self.assertEqual(objs[1].date, date(2016, 6, 16))
        self.assertEqual(objs[1].amount, Decimal('10.91'))
        self.assertEqual(objs[1].description, 'Another payment')

        self.assertEqual(objs[2].date, date(2016, 6, 17))
        self.assertEqual(objs[2].amount, Decimal('-1.23'))
        self.assertEqual(objs[2].description, 'Paying someone')

    def test_import_a_few_with_identical_transactions(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '5.10', 'Example payment'],
            ['16/6/2016', '10.91', 'Another payment'],
            ['16/6/2016', '10.91', 'Another payment'],
            ['17/6/2016', '-1.23', 'Paying someone'],
            headers=['date', 'amount', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 4)
        objs = StatementLine.objects.all().order_by('pk')

        self.assertEqual(objs[0].date, date(2016, 6, 15))
        self.assertEqual(objs[0].amount, Decimal('5.10'))
        self.assertEqual(objs[0].description, 'Example payment')

        self.assertEqual(objs[1].date, date(2016, 6, 16))
        self.assertEqual(objs[1].amount, Decimal('10.91'))
        self.assertEqual(objs[1].description, 'Another payment')

        self.assertEqual(objs[2].date, date(2016, 6, 16))
        self.assertEqual(objs[2].amount, Decimal('10.91'))
        self.assertEqual(objs[2].description, 'Another payment')

        self.assertEqual(objs[3].date, date(2016, 6, 17))
        self.assertEqual(objs[3].amount, Decimal('-1.23'))
        self.assertEqual(objs[3].description, 'Paying someone')

    def test_split_amounts(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '', '100.56', 'Example payment'],
            ['16/6/2016', '60.31', '', 'Example income'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        self.makeResource().import_data(dataset)

        self.assertEqual(StatementLine.objects.count(), 2)

        obj = StatementLine.objects.all().order_by('date')
        self.assertEqual(obj[0].date, date(2016, 6, 15))
        self.assertEqual(obj[0].amount, Decimal('-100.56'))
        self.assertEqual(obj[0].description, 'Example payment')

        self.assertEqual(obj[1].date, date(2016, 6, 16))
        self.assertEqual(obj[1].amount, Decimal('60.31'))
        self.assertEqual(obj[1].description, 'Example income')

    def test_error_no_date(self):
        dataset = tablib.Dataset(
            ['5.10', 'Example payment'],
            headers=['amount', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('No date', str(result.row_errors()[0][1][0].error))

    def test_error_empty_date(self):
        dataset = tablib.Dataset(
            ['', '5.10', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Expected dd/mm/yyyy', str(result.row_errors()[0][1][0].error))

    def test_error_empty_amounts(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '', '', 'Example payment'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Value required', str(result.row_errors()[0][1][0].error))

    def test_error_empty_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('No value found', str(result.row_errors()[0][1][0].error))

    def test_error_both_amounts(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '5.10', '1.20', 'Example payment'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Values found for both', str(result.row_errors()[0][1][0].error))

    def test_error_neither_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '', '', 'Example payment'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('either', str(result.row_errors()[0][1][0].error))

    def test_error_invalid_in_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', 'a', '', 'Example payment'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Invalid', str(result.row_errors()[0][1][0].error))

    def test_error_invalid_out_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '', 'a', 'Example payment'],
            headers=['date', 'amount_in', 'amount_out', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Invalid', str(result.row_errors()[0][1][0].error))

    def test_error_invalid_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', 'a', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('Invalid', str(result.row_errors()[0][1][0].error))

    def test_error_no_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', 'Example payment'],
            headers=['date', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('No amount', str(result.row_errors()[0][1][0].error))

    def test_error_zero_amount(self):
        dataset = tablib.Dataset(
            ['15/6/2016', '0', 'Example payment'],
            headers=['date', 'amount', 'description']
        )
        result = self.makeResource().import_data(dataset)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertIn('zero not allowed', str(result.row_errors()[0][1][0].error))


class DryRunViewTestCase(DataProvider, TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.INFO)

    def create_import(self, year=b'2000'):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/' + year + b',123456789,123,OTH,Some random notes')
                               )
        self.transaction_import = TransactionImport.objects.create(
            has_headings=True,
            file=f,
            date_format='%d/%m/%Y',
            hordak_import=self.statement_import(),
        )
        self.view_url = reverse('transactions:import_dry_run', args=[self.transaction_import.uuid])
        self.transaction_import.create_columns()

        self.transaction_import.columns.filter(column_number=2).update(to_field='date')
        self.transaction_import.columns.filter(column_number=4).update(to_field='amount')
        self.transaction_import.columns.filter(column_number=6).update(to_field='description')

    def test_get(self):
        self.create_import()

        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(StatementLine.objects.count(), 0)

    def test_post(self):
        self.create_import()

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 0, result.failed_dataset.dict)
        self.assertEqual(result.base_errors, [])
        self.assertEqual(result.totals['new'], 1)
        self.assertEqual(result.totals['update'], 0)
        self.assertEqual(result.totals['delete'], 0)
        self.assertEqual(result.totals['skip'], 0)
        self.assertEqual(result.totals['error'], 0)

        self.assertEqual(StatementLine.objects.count(), 0)

    def test_date_error(self):
        self.create_import(b'1')

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 1, result.failed_dataset.dict)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertEqual(StatementLine.objects.count(), 0)


class ExecuteViewTestCase(DataProvider, TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.INFO)

    def create_import(self, year=b'2000'):
        f = SimpleUploadedFile('data.csv',
                               six.binary_type(
                                   b'Number,Date,Account,Amount,Subcategory,Memo\n'
                                   b'1,1/1/' + year + b',123456789,123,OTH,Some random notes')
                               )
        self.transaction_import = TransactionImport.objects.create(
            has_headings=True,
            file=f,
            date_format='%d/%m/%Y',
            hordak_import=self.statement_import()
        )
        self.view_url = reverse('transactions:import_execute', args=[self.transaction_import.uuid])
        self.transaction_import.create_columns()

        self.transaction_import.columns.filter(column_number=2).update(to_field='date')
        self.transaction_import.columns.filter(column_number=4).update(to_field='amount')
        self.transaction_import.columns.filter(column_number=6).update(to_field='description')

    def test_get(self):
        self.create_import()

        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StatementLine.objects.count(), 0)

    def test_post(self):
        self.create_import()

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 0, result.failed_dataset.dict)
        self.assertEqual(result.base_errors, [])
        self.assertEqual(result.totals['new'], 1)
        self.assertEqual(result.totals['update'], 0)
        self.assertEqual(result.totals['delete'], 0)
        self.assertEqual(result.totals['skip'], 0)
        self.assertEqual(result.totals['error'], 0)

        self.assertEqual(StatementLine.objects.count(), 1)

    def test_date_error(self):
        self.create_import(b'1')

        response = self.client.post(self.view_url)
        result = response.context['result']

        self.assertEqual(len(result.failed_dataset), 1, result.failed_dataset.dict)
        self.assertEqual(len(result.row_errors()), 1)
        self.assertEqual(StatementLine.objects.count(), 0)


class TransactionImportFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.f = SimpleUploadedFile('data.csv',
                                    six.binary_type(b'Number,Date,Account,Amount,Subcategory,Memo'))

    def test_create(self):
        form = TransactionImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        obj = TransactionImport.objects.get()
        self.assertEqual(obj.columns.count(), 6)
        self.assertEqual(obj.hordak_import.bank_account, self.account)

    def test_edit(self):
        obj = TransactionImport.objects.create(
            hordak_import=self.statement_import(bank_account=self.account),
            has_headings=True,
            file=self.f
        )
        form = TransactionImportForm(data=dict(bank_account=self.account.pk), files=dict(file=self.f), instance=obj)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(obj.columns.count(), 0)
