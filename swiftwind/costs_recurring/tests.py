from decimal import Decimal

from django.test import TestCase
from django.urls.base import reverse
from hordak.models import Account

from swiftwind.costs_recurring.forms import RecurringCostForm
from swiftwind.costs_recurring.models import RecurringCost, RecurringCostSplit


class RecurringCostFormTestCase(TestCase):

    def setUp(self):
        self.expense_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.housemate_parent_account = Account.objects.create(name='Housemate Income', code='2', type=Account.TYPES.income)
        self.housemate_1 = Account.objects.create(name='Housemate 1', code='1', parent=self.housemate_parent_account)
        self.housemate_2 = Account.objects.create(name='Housemate 2', code='2', parent=self.housemate_parent_account)
        self.housemate_3 = Account.objects.create(name='Housemate 3', code='3', parent=self.housemate_parent_account)

    def test_valid(self):
        form = RecurringCostForm(data=dict(
            to_account=self.expense_account.uuid,
            type=RecurringCost.TYPES.normal,
            is_active='yes',
            fixed_amount='100',
            total_billing_cycles='5',
        ))
        self.assertTrue(form.is_valid())
        obj = form.save()
        obj.refresh_from_db()
        self.assertEqual(obj.to_account, self.expense_account)
        self.assertEqual(obj.type, RecurringCost.TYPES.normal)
        self.assertEqual(obj.is_active, True)
        self.assertEqual(obj.fixed_amount, Decimal('100'))
        self.assertEqual(obj.total_billing_cycles, 5)

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
            is_active='yes',
            fixed_amount='100',
            total_billing_cycles='5',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('fixed_amount', form.errors)


class RecurringCostsViewTestCase(TestCase):

    def setUp(self):
        self.expense_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.housemate_parent_account = Account.objects.create(name='Housemate Income', code='2', type=Account.TYPES.income)
        self.housemate_1 = Account.objects.create(name='Housemate 1', code='1', parent=self.housemate_parent_account)
        self.housemate_2 = Account.objects.create(name='Housemate 2', code='2', parent=self.housemate_parent_account)
        self.housemate_3 = Account.objects.create(name='Housemate 3', code='3', parent=self.housemate_parent_account)

        self.recurring_cost_1 = RecurringCost.objects.create(to_account=self.expense_account, fixed_amount=100)
        RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_1)
        RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_2)
        RecurringCostSplit.objects.create(recurring_cost=self.recurring_cost_1, from_account=self.housemate_3)

        self.view_url = reverse('costs_recurring:list')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('formset', context)


