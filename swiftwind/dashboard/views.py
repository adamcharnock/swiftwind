from django.db.models import Q
from django.shortcuts import render
from django.views.generic import TemplateView
from hordak.models import Account


class DashboardView(TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_balance_context(self):
        """Get the high level balances"""
        income_accounts = Account.objects.filter(_type=Account.TYPES.income)
        expense_accounts = Account.objects.filter(_type=Account.TYPES.expense)

        net_income = income_accounts.net_balance()
        net_expense = expense_accounts.net_balance()

        return dict(
            net_income=net_income,
            net_expense=net_expense,
            net_total=net_income - net_expense,
            bank_balance=Account.objects.get(name='Bank').balance(),
            retained_earnings_balance=Account.objects.get(name='Retained Earnings').balance(),
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
            expense_accounts=Account.objects.filter(parent=expense_parent),
            current_liability_accounts=Account.objects.filter(parent=current_liabilities_parent),
            long_term_liability_accounts=Account.objects.filter(parent=long_term_liabilities_parent),
            other_income_accounts=Account.objects.filter(~Q(pk=housemate_parent.pk), parent=income_parent)
        )


    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data()

        context.update(**self.get_balance_context())
        context.update(**self.get_accounts_context())

        return context
