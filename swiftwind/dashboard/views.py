from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import TemplateView
from django.conf import settings
from hordak.models import Account
from hordak.utilities.currency import Balance


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_balance_context(self):
        """Get the high level balances"""
        income_accounts = Account.objects.filter(type=Account.TYPES.income, children__isnull=True)
        expense_accounts = Account.objects.filter(type=Account.TYPES.expense, children__isnull=True)
        bank_account = Account.objects.get(name='Bank')

        net_income = income_accounts.net_balance()
        net_expense = expense_accounts.net_balance()
        net_total = net_income - net_expense

        # Ensure we have a zero value if we have no income or expense accounts
        if not net_total.monies():
            net_total += Balance('0', settings.SWIFTWIND_DEFAULT_CURRENCY)

        return dict(
            net_income=net_income,
            net_expense=net_expense,
            net_total=net_total,
            bank=bank_account,
            retained_earnings=Account.objects.get(name='Retained Earnings'),
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
