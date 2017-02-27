from django.test.testcases import TestCase

from swiftwind.core.management.commands.swiftwind_create_accounts import Command as CreateChartOfAccountsCommand
from hordak.models.core import Account
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
