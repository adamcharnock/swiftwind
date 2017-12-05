import six
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.core import mail
from datetime import date
from unittest.mock import patch

from django.urls.base import reverse
from django.utils.timezone import datetime
from freezegun.api import freeze_time

from hordak.models.core import StatementImport, Account, StatementLine, Transaction
from pytz import UTC

from swiftwind.costs.models import RecurringCost, RecurringCostSplit
from swiftwind.utilities.testing import DataProvider

from .cycles import Monthly
from .models import BillingCycle


class BillingCycleConstraintTestCase(TransactionTestCase):

    def test_constraint_non_overlapping(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 1, 25), date(2016, 2, 25))
            )

    def test_constraint_adjacent(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 2, 2), date(2016, 3, 1))
            )

    def test_constraint_ok(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        BillingCycle.objects.create(
            date_range=(date(2016, 2, 1), date(2016, 3, 1))
        )
        # No errors


class BillingCycleTestCase(DataProvider, TransactionTestCase):

    def test_populate_no_cycles(self):
        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 1), delete=False)

        self.assertEqual(BillingCycle.objects.count(), 25)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 6, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

    def test_populate_update_only(self):
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))  # keep
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))  # keep
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))  # keep
        cycle4 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))  # keep

        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 1), delete=False)

        # 4 previous cycles kept, 1 not created, and 24 new ones created
        self.assertEqual(BillingCycle.objects.count(), 4 + 23)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 4, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

        self.assertIn(cycle1, BillingCycle.objects.all())
        self.assertIn(cycle2, BillingCycle.objects.all())
        self.assertIn(cycle3, BillingCycle.objects.all())
        self.assertIn(cycle4, BillingCycle.objects.all())

    def test_populate_delete(self):
        """Check that future billing cycles get deleted and recreated"""
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))  # keep
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))  # keep
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))  # keep
        cycle4 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))  # delete

        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 15), delete=True)

        # 3 previous cycles kept, and 24 new ones created
        self.assertEqual(BillingCycle.objects.filter(start_date__gte=date(2016, 7, 1)).count(), 24)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 4, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

        self.assertIn(cycle1, BillingCycle.objects.all())
        self.assertIn(cycle2, BillingCycle.objects.all())
        self.assertIn(cycle3, BillingCycle.objects.all())
        self.assertNotIn(cycle4, BillingCycle.objects.all())

    def test_is_reconciled_true(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        statement_line.create_transaction(to_account=other_account)

        self.assertTrue(billing_cycle.is_reconciled())

    def test_is_reconciled_no_statement_lines(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank,
            source='csv',
        )

        self.assertTrue(billing_cycle.is_reconciled())

    def test_is_reconciled_no_transaction(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            bank_account=bank,
            source='csv',
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        # No transaction created

        self.assertFalse(billing_cycle.is_reconciled())

    def test_is_reconciled_old_import(self):
        bank = self.account(name='Bank', type=Account.TYPES.asset)
        other_account = self.account()
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        statement_import = StatementImport.objects.create(
            timestamp=datetime(2016, 4, 25, 9, 30, 00, tzinfo=UTC),
            bank_account=bank,
            source='csv',
        )
        statement_line = StatementLine.objects.create(
            timestamp=datetime(2016, 5, 1, 9, 30, 00, tzinfo=UTC),
            date=date(2016, 4, 10),
            statement_import=statement_import,
            amount=10,
        )
        # No transaction created

        self.assertFalse(billing_cycle.is_reconciled())

    def test_send_reconciliation_required(self):
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        self.housemate(user_kwargs=dict(email='user@example.com'))
        billing_cycle.send_reconciliation_required()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ['user@example.com'])
        content, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<html', content)

    def test_send_statements(self):
        billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        billing_cycle.refresh_from_db()
        self.housemate(user_kwargs=dict(email='user@example.com'))
        billing_cycle.send_statements(force=True)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].recipients(), ['user@example.com'])
        content, mime = mail.outbox[0].alternatives[0]
        self.assertEqual(mime, 'text/html')
        self.assertIn('<html', content)


class CycleTestCase(TestCase):

    def test_monthly_get_previous_cycle_start_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_previous_cycle_start_date(date(2016, 6, 15), inclusive=True),
            date(2016, 6, 1)
        )
        self.assertEqual(
            cycle.get_previous_cycle_start_date(date(2016, 6, 1), inclusive=True),
            date(2016, 6, 1)
        )

    def test_monthly_get_next_cycle_start_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 15), inclusive=True),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 1), inclusive=True),
            date(2016, 6, 1)
        )

    def test_monthly_get_cycle_end_date(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 15)),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 1)),
            date(2016, 7, 1)
        )

    def test_monthly_generate_date_ranges(self):
        cycle = Monthly()

        ranges = cycle.generate_date_ranges(date(2016, 10, 15))
        self.assertEqual(six.next(ranges), (date(2016, 10, 1), date(2016, 11, 1)))  # starts in Oct
        self.assertEqual(six.next(ranges), (date(2016, 11, 1), date(2016, 12, 1)))
        self.assertEqual(six.next(ranges), (date(2016, 12, 1), date(2017, 1, 1)))

    def test_monthly_generate_date_ranges_omit_current(self):
        cycle = Monthly()

        ranges = cycle.generate_date_ranges(date(2016, 10, 15), omit_current=True)
        self.assertEqual(six.next(ranges), (date(2016, 11, 1), date(2016, 12, 1)))  # starts in Nov
        self.assertEqual(six.next(ranges), (date(2016, 12, 1), date(2017, 1, 1)))
        self.assertEqual(six.next(ranges), (date(2017, 1, 1), date(2017, 2, 1)))


class BillingCycleListViewTestCase(DataProvider, TestCase):

    def test_get(self):
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 8, 1), date(2016, 9, 1)))

        with freeze_time('2016-06-15'):
            response = self.client.get(reverse('billing_cycles:list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['billing_cycles']), 3)


class CreateTransactionsViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.housemate1 = self.housemate(account_kwargs=dict(currencies=['GBP']))
        self.housemate2 = self.housemate(account_kwargs=dict(currencies=['GBP']))

        self.billing_cycle = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        self.billing_cycle.refresh_from_db()

        self.to_account = self.account(currencies=['GBP'])
        with transaction.atomic():
            self.recurring_cost = RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.normal,
                initial_billing_cycle=self.billing_cycle,
            )
            RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost, from_account=self.housemate1.account)
            RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost, from_account=self.housemate2.account)

    @patch.object(BillingCycle, 'send_statements')
    def test_transactions_not_yet_created(self, mock):
        response = self.client.post(reverse('billing_cycles:enact', args=[self.billing_cycle.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 1)  # One transaction per recurring cost

        self.billing_cycle.refresh_from_db()
        self.assertEqual(self.billing_cycle.transactions_created, True)

    @patch.object(BillingCycle, 'send_statements')
    def test_already_enacted(self, mock):
        self.billing_cycle.enact_all_costs()
        self.assertEqual(Transaction.objects.count(), 1)

        response = self.client.post(reverse('billing_cycles:enact', args=[self.billing_cycle.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 1)


class SendNotificationsViewTestCase(DataProvider, TestCase):

    @patch.object(BillingCycle, 'send_statements')
    def test_transactions_not_yet_created(self, mock):
        self.housemate()
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        response = self.client.post(reverse('billing_cycles:send', args=[cycle1.uuid]))
        self.assertEqual(response.status_code, 302)
        mock.assert_not_called()

    @patch.object(BillingCycle, 'send_statements')
    def test_transactions_created(self, mock):
        self.housemate()
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))
        cycle1.transactions_created = True
        cycle1.save()
        response = self.client.post(reverse('billing_cycles:send', args=[cycle1.uuid]))
        self.assertEqual(response.status_code, 302)
        mock.assert_called()

