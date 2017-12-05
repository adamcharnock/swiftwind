from django.test.testcases import TestCase

from swiftwind.core.exceptions import CannotCreateMultipleSettingsInstances
from swiftwind.core.management.commands.swiftwind_create_accounts import Command as CreateChartOfAccountsCommand
from hordak.models.core import Account
from swiftwind.settings.models import Settings
from swiftwind.utilities.testing import DataProvider


class CreateChartOfAccountsCommandTestCase(DataProvider, TestCase):

    def test_create(self):
        CreateChartOfAccountsCommand().handle()
        self.assertTrue(Account.objects.count() > 10)

    def test_create_currency(self):
        CreateChartOfAccountsCommand().handle(currency='GBP')
        self.assertEqual(Account.objects.get(name='Income').currencies, ['GBP'])

    def test_preserve(self):
        CreateChartOfAccountsCommand().handle(preserve=True)
        self.assertTrue(Account.objects.count() > 10)

    def test_preserve_with_existing_account(self):
        self.account()
        CreateChartOfAccountsCommand().handle(preserve=True)
        self.assertTrue(Account.objects.count() > 10)


class SettingsTestCase(TestCase):

    def test_get_creates(self):
        settings = Settings.objects.get()
        self.assertEqual(Settings.objects.count(), 1)
        self.assertEqual(settings.default_currency, 'EUR')

    def test_get(self):
        # First create
        Settings.objects.get()
        self.assertEqual(Settings.objects.count(), 1)
        # Now get
        settings = Settings.objects.get()
        self.assertEqual(settings.default_currency, 'EUR')

    def test_get_create_error(self):
        # Cannot create a second instance
        Settings.objects.get()
        with self.assertRaises(CannotCreateMultipleSettingsInstances):
            Settings.objects.create()
