from celery import shared_task
from django.db import transaction

from hordak.data_sources import tellerio
from hordak.models.core import Account
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.settings.models import Settings


@shared_task
@transaction.atomic()
def notify_housemates():
    for billing_cycle in BillingCycle.objects.filter(transactions_created=True, statements_sent=False):
        billing_cycle.notify_housemates()


@shared_task
@transaction.atomic()
def import_tellerio():
    settings = Settings.objects.get()

    if settings.tellerio_enable:
        first_billing_cycle = BillingCycle.objects.first()
        tellerio.do_import(
            token=settings.tellerio_token,
            account_uuid=settings.tellerio_account_id,
            bank_account=Account.objects.filter(is_bank_account=True)[0],
            since=first_billing_cycle.date_range.lower,
        )
        return True
    else:
        return False
