from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import TemplateView
from django.conf import settings
from hordak.models import Account
from hordak.utilities.currency import Balance
from swiftwind.billing_cycle.models import BillingCycle


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_balance_context(self):
        """Get the high level balances"""
        bank_account = Account.objects.get(name='Bank')

        return dict(
            bank=bank_account,
            retained_earnings_accounts=Account.objects.filter(parent__name='Retained Earnings'),
        )

    def get_accounts_context(self):
        """Get the accounts we may want to display"""
        income_parent = Account.objects.get(name='Income')
        housemate_parent = Account.objects.get(name='Housemate Income')
        expense_parent = Account.objects.get(name='Expenses')
        current_liabilities_parent = Account.objects.get(name='Current Liabilities')
        long_term_liabilities_parent = Account.objects.get(name='Long Term Liabilities')

        return dict(
            housemate_accounts=Account.objects.filter(parent=housemate_parent),
            expense_accounts=expense_parent.get_descendants(),
            current_liability_accounts=Account.objects.filter(parent=current_liabilities_parent),
            long_term_liability_accounts=Account.objects.filter(parent=long_term_liabilities_parent),
            other_income_accounts=Account.objects.filter(~Q(pk=housemate_parent.pk), parent=income_parent)
        )

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data()

        context.update(**self.get_balance_context())
        context.update(**self.get_accounts_context())

        return context
