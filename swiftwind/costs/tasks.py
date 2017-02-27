from datetime import date

from celery import shared_task
from django.db import transaction

from swiftwind.costs.models import RecurringCost


@shared_task
@transaction.atomic()
def enact_costs(as_of=None):
    if as_of is None:
        as_of = date.today()
    RecurringCost.objects.all().enact(as_of)
