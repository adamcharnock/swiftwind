from celery import shared_task
from django.db import transaction

from swiftwind.billing_cycle.models import BillingCycle


@shared_task
@transaction.atomic()
def send_statements():
    for billing_cycle in BillingCycle.objects.filter(transactions_created=True, statements_sent=False):
        pass  # TODO
