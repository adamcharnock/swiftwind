from django.core.management.base import BaseCommand, CommandError

from swiftwind.accounts.tasks import import_tellerio


class Command(BaseCommand):
    help = 'Import bank statements from teller.io. Configure in settings.'

    def handle(self, *args, **options):
        done = import_tellerio()
        if not done:
            raise CommandError('teller.io imports are not enabled. Enable them in the web interface.')
