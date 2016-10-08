from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase
from django.urls.base import reverse
from hordak.models import Account

from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.costs.models import RecurredCost
from .forms import RecurringCostForm
from .models import RecurringCost, RecurringCostSplit


class RecurringCostModelTestCase(TestCase):

    def setUp(self):
        self.bank = Account.objects.create(name='Bank', code='0', type=Account.TYPES.asset)
        self.to_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.billing_cycle_1 = BillingCycle.objects.create(date_range=('2000-01-01', '2000-02-01'))
        self.billing_cycle_2 = BillingCycle.objects.create(date_range=('2000-02-01', '2000-03-01'))
        self.billing_cycle_3 = BillingCycle.objects.create(date_range=('2000-03-01', '2000-04-01'))
        self.billing_cycle_4 = BillingCycle.objects.create(date_range=('2000-04-01', '2000-05-01'))

    # Recurring costs

    def test_recurring_normal_no_recurrences(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
        )
        recurring_cost.enact(self.billing_cycle_1)
        recurring_cost.enact(self.billing_cycle_2)

        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 100)

        self.assertEqual(recurring_cost.get_billed_amount(), 200)

        self.assertEqual(recurring_cost.is_one_off(), False)
        self.assertEqual(recurring_cost._is_finished(), False)

        # Billing is never complete for regular recurring costs
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), True)

    def test_recurring_normal_two_recurrences(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
        )
        recurring_cost.enact(self.billing_cycle_1)
        recurring_cost.enact(self.billing_cycle_2)

        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 100)

        self.assertEqual(recurring_cost.get_billed_amount(), 200)

        self.assertEqual(recurring_cost.is_one_off(), False)
        self.assertEqual(recurring_cost._is_finished(), False)

        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), True)

    def test_recurring_disabled(self):
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            disbled=True,
        )
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 100)

        self.assertEqual(recurring_cost.get_billed_amount(), 0)

        self.assertEqual(recurring_cost.is_one_off(), False)
        self.assertEqual(recurring_cost._is_finished(), False)

        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), False)

    def test_recurring_arrears_balance(self):
        self.to_account.transfer_to(self.bank, 100, date='2000-01-15')
        self.to_account.transfer_to(self.bank, 50, date='2000-02-15')

        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            type=RecurringCost.TYPES.arrears_balance,
            disbled=True,
        )
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 150)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 0)

    def test_recurring_arrears_transactions(self):
        self.to_account.transfer_to(self.bank, 100, date='2000-01-15')
        self.to_account.transfer_to(self.bank, 50, date='2000-02-15')

        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            type=RecurringCost.TYPES.arrears_transactions,
            disbled=True,
        )
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 100)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 50)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 0)

    # One-off costs

    def test_one_off_no_recurrences(self):
        """One-off with no recurrences done"""
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            total_billing_cycles=2,  # Makes this a one-off cost
        )
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 33.34)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_4), 0)

        self.assertEqual(recurring_cost.get_billed_amount(), 0)

        self.assertEqual(recurring_cost.is_one_off(), True)
        self.assertEqual(recurring_cost._is_finished(), False)

        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_4), True)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_4), False)

    def test_one_off_with_some_recurrences(self):
        """One-off with one recurrences done"""
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            total_billing_cycles=3,  # Makes this a one-off cost
        )
        recurring_cost.enact(self.billing_cycle_1)

        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 33.34)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_4), 0)

        self.assertEqual(recurring_cost.get_billed_amount(), 33.33)

        self.assertEqual(recurring_cost.is_one_off(), True)
        self.assertEqual(recurring_cost._is_finished(), False)

        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_4), True)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_4), False)

    def test_one_off_complete(self):
        """One-off cost with all recurrences done"""
        recurring_cost = RecurringCost.objects.create(
            to_account=self.to_account,
            fixed_amount=100,
            type=RecurringCost.TYPES.normal,
            total_billing_cycles=3,  # Makes this a one-off cost
        )
        recurring_cost.enact(self.billing_cycle_1)
        recurring_cost.enact(self.billing_cycle_2)
        recurring_cost.enact(self.billing_cycle_3)

        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_1), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_2), 33.33)
        self.assertEqual(recurring_cost.get_amount(self.billing_cycle_3), 33.34)

        self.assertEqual(recurring_cost.get_billed_amount(), 100)

        self.assertEqual(recurring_cost.is_one_off(), True)
        self.assertEqual(recurring_cost._is_finished(), False)

        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_1), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_2), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_3), False)
        self.assertEqual(recurring_cost._is_billing_complete(self.billing_cycle_4), True)

        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_1), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_2), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_3), True)
        self.assertEqual(recurring_cost.is_enactable(self.billing_cycle_4), False)

    def test_one_off_arrears_balance(self):
        with self.assertRaises(IntegrityError):
            RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.arrears_balance,
                total_billing_cycles=2,
            )

    def test_one_off_arrears_transactions(self):
        with self.assertRaises(IntegrityError):
            RecurringCost.objects.create(
                to_account=self.to_account,
                fixed_amount=100,
                type=RecurringCost.TYPES.arrears_transactions,
                total_billing_cycles=2,
            )






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
            disabled='',
            fixed_amount='100',
        ))
        self.assertTrue(form.is_valid())
        obj = form.save()
        obj.refresh_from_db()
        self.assertEqual(obj.to_account, self.expense_account)
        self.assertEqual(obj.type, RecurringCost.TYPES.normal)
        self.assertEqual(obj.disabled, False)
        self.assertEqual(obj.fixed_amount, Decimal('100'))

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
            'form-0-fixed_amount': Decimal('200'),
            'form-0-disabled': 'o',
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
            self.assertFalse(context['formset'].all_errors())

        self.recurring_cost_1.refresh_from_db()
        self.assertEqual(self.recurring_cost_1.fixed_amount, 200)

        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()

        self.assertEqual(self.split1.portion, 2)
        self.assertEqual(self.split2.portion, 3)
        self.assertEqual(self.split3.portion, 4)


class CreateRecurringCostViewTestCase(TestCase):

    def setUp(self):
        self.expense_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.housemate_parent_account = Account.objects.create(name='Housemate Income', code='2', type=Account.TYPES.income)
        self.housemate_1 = Account.objects.create(name='Housemate 1', code='1', parent=self.housemate_parent_account)
        self.housemate_2 = Account.objects.create(name='Housemate 2', code='2', parent=self.housemate_parent_account)
        self.housemate_3 = Account.objects.create(name='Housemate 3', code='3', parent=self.housemate_parent_account)

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
        })
        context = response.context
        if response.context:
            self.assertFalse(context['formset'].all_errors())

        self.assertEqual(RecurringCost.objects.count(), 1)
        recurring_cost = RecurringCost.objects.get()
        self.assertEqual(recurring_cost.to_account, self.expense_account)
        self.assertEqual(recurring_cost.total_billing_cycles, None)
        self.assertEqual(recurring_cost.fixed_amount, 200)
        self.assertEqual(recurring_cost.disabled, False)

        self.assertEqual(recurring_cost.splits.count(), 3)


class OneOffCostsViewTestCase(TestCase):

    def setUp(self):
        self.expense_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.housemate_parent_account = Account.objects.create(name='Housemate Income', code='2', type=Account.TYPES.income)
        self.housemate_1 = Account.objects.create(name='Housemate 1', code='1', parent=self.housemate_parent_account)
        self.housemate_2 = Account.objects.create(name='Housemate 2', code='2', parent=self.housemate_parent_account)
        self.housemate_3 = Account.objects.create(name='Housemate 3', code='3', parent=self.housemate_parent_account)

        self.recurring_cost_1 = RecurringCost.objects.create(to_account=self.expense_account, fixed_amount=100, total_billing_cycles=2)
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
            self.assertFalse(context['formset'].all_errors())

        self.recurring_cost_1.refresh_from_db()
        self.assertEqual(self.recurring_cost_1.total_billing_cycles, 3)
        self.assertEqual(self.recurring_cost_1.fixed_amount, 200)

        self.split1.refresh_from_db()
        self.split2.refresh_from_db()
        self.split3.refresh_from_db()

        self.assertEqual(self.split1.portion, 2)
        self.assertEqual(self.split2.portion, 3)
        self.assertEqual(self.split3.portion, 4)


class CreateOneOffCostViewTestCase(TestCase):

    def setUp(self):
        self.expense_account = Account.objects.create(name='Expense', code='1', type=Account.TYPES.expense)
        self.housemate_parent_account = Account.objects.create(name='Housemate Income', code='2', type=Account.TYPES.income)
        self.housemate_1 = Account.objects.create(name='Housemate 1', code='1', parent=self.housemate_parent_account)
        self.housemate_2 = Account.objects.create(name='Housemate 2', code='2', parent=self.housemate_parent_account)
        self.housemate_3 = Account.objects.create(name='Housemate 3', code='3', parent=self.housemate_parent_account)

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
        })
        context = response.context
        if response.context:
            self.assertFalse(context['formset'].all_errors())

        self.assertEqual(RecurringCost.objects.count(), 1)
        recurring_cost = RecurringCost.objects.get()
        self.assertEqual(recurring_cost.to_account, self.expense_account)
        self.assertEqual(recurring_cost.total_billing_cycles, 2)
        self.assertEqual(recurring_cost.fixed_amount, 200)
        self.assertEqual(recurring_cost.disabled, False)

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



