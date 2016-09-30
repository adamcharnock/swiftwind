from celery import shared_task

from .models import BillingCycle


@shared_task
def populate_billing_cycles():
    BillingCycle.populate()
