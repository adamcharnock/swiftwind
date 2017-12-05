from datetime import date

from celery import shared_task
from django.db import transaction

from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.costs.models import RecurringCost


@shared_task
@transaction.atomic()
def enact_costs(as_of=None):
    if as_of is None:
        as_of = date.today()
    for billing_cycle in BillingCycle.objects.filter(start_date__lt=as_of, transactions_created=False):
        billing_cycle.enact_all_costs()


@shared_task
@transaction.atomic()
def disable_costs():
    """Disable any costs that have completed all their billing cycles"""
    RecurringCost.objects.all().disable_if_done()


