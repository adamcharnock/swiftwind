from django.core.management.base import BaseCommand

from swiftwind.billing_cycle.models import BillingCycle


class Command(BaseCommand):
    help = 'Populate billing cycles'

    def handle(self, *args, **options):
        BillingCycle.populate()
