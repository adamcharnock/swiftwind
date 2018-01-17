import logging
import schedule
import time
from django.core.management.base import BaseCommand

from swiftwind.accounts.tasks import import_tellerio

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the scheduler which executes periodic tasks'

    def handle(self, *args, **options):

        schedule.every().hour.do(import_tellerio)

        while True:
            schedule.run_pending()
            time.sleep(1)
