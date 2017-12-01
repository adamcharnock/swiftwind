from datetime import date

from django.db import models
from django.db.models import Q, Sum, When, Case, Value, Subquery, OuterRef, Exists
from django.db.models.functions import Cast
from django.views.generic.list import ListView
from djmoney.models.fields import MoneyField

from hordak.models.core import Account, Transaction, Leg
from swiftwind.billing_cycle.models import BillingCycle


class OverviewView(ListView):
    template_name = 'accounts/overview.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        housemate_income = Account.objects.get(name='Housemate Income')
        expenses = Account.objects.get(name='Expenses')
        current_billing_cycle = BillingCycle.objects.as_of(date.today())

        money_field = MoneyField(
            max_digits=13,
            decimal_places=2,
            currency_field_name='currency'
        )

        return Account.objects.filter(

            # We want any account under 'Housemate Income' or 'Expenses'
            Q(lft__gt=housemate_income.lft, rght__lt=housemate_income.rght, tree_id=housemate_income.tree_id)
            |
            Q(lft__gt=expenses.lft, rght__lt=expenses.rght, tree_id=expenses.tree_id)

        ).filter(
            # We only want leaf accounts (no accounts that contain other accounts)
            children__isnull=True

        ).annotate(
            # Is this an expense or housemate account?
            display_type=Case(
                When(housemate__isnull=True, then=Value('expense')),
                default=Value('housemate'),
                output_field=models.CharField()
            )

        ).annotate(
            # When was the last transaction
            latest_transaction_date=Subquery(
                Transaction.objects.filter(legs__account=OuterRef('pk')).order_by('-date').values('date')[:1]
            )

        ).annotate(
            # Has there been a payment during this billing cycle
            payment_since_last_bill=Exists(
                Transaction.objects.filter(
                    legs__amount__gt=0,
                    legs__account=OuterRef('pk'),
                    date__gte=current_billing_cycle.date_range.lower
                )
            )

        )\
            .order_by('-display_type')


