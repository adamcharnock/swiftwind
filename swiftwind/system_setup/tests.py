from datetime import date
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from hordak.models.core import Account, Transaction
from hordak.utilities.currency import Balance
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.settings.models import Settings
from swiftwind.housemates.models import Housemate
from swiftwind.utilities.testing import DataProvider


class SetupViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.view_url = reverse('setup:index')

    @override_settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
    def test_get(self):
        response = self.client.get(self.view_url,
                                   HTTP_HOST='mysite.com',
                                   SERVER_PORT=8080,
                                   HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('form', context)
        self.assertEqual(context['form']['site_domain'].initial, 'mysite.com:8080')
        self.assertEqual(context['form']['use_https'].initial, True)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'first_name': 'First',
            'last_name': 'Last',
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'mypassword',
            'password2': 'mypassword',
            'default_currency': 'GBP',
            'additional_currencies': ['EUR', 'USD'],
            'site_name': 'My Site',
            'site_domain': 'mysite.com',
            'use_https': 'yes',
            'opening_bank_balance': '0.00',
            'accounting_start_date': '2000-01-01',
        })
        context = response.context
        if response.context:
            self.assertFalse(context['form'].errors)

        user = User.objects.get()
        self.assertEqual(user.first_name, 'First')
        self.assertEqual(user.last_name, 'Last')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('mypassword'))
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

        settings = Settings.objects.get()
        self.assertEqual(settings.default_currency, 'GBP')
        self.assertEqual(settings.additional_currencies, ['EUR', 'USD'])
        self.assertTrue(settings.use_https)

        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

        housemate = Housemate.objects.get()
        self.assertEqual(housemate.user, user)
        self.assertEqual(housemate.account.type, Account.TYPES.income)

        site = Site.objects.get()
        self.assertEqual(site.domain, 'mysite.com')
        self.assertEqual(site.name, 'My Site')

        # Check no opening balance account has been created
        self.assertFalse(Account.objects.filter(name='Opening Balance').exists())
        self.assertFalse(Transaction.objects.all().exists())

        # Check accounting start date was used
        self.assertEqual(BillingCycle.objects.first().date_range.lower, date(2000, 1, 1))
        self.assertEqual(BillingCycle.objects.first().date_range.upper, date(2000, 2, 1))

    def test_can_load_dashboard_after_setup(self):
        self.client.post(self.view_url, data={
            'first_name': 'First',
            'last_name': 'Last',
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'mypassword',
            'password2': 'mypassword',
            'default_currency': 'GBP',
            'additional_currencies': ['EUR', 'USD'],
            'site_name': 'My Site',
            'site_domain': 'mysite.com',
            'use_https': 'yes',
            'opening_bank_balance': '0.00',
            'accounting_start_date': '2000-01-01',
        })

        # Now check we can load the dashboard
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_post_opening_balance(self):
        response = self.client.post(self.view_url, data={
            'first_name': 'First',
            'last_name': 'Last',
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'mypassword',
            'password2': 'mypassword',
            'default_currency': 'GBP',
            'additional_currencies': ['EUR', 'USD'],
            'site_name': 'My Site',
            'site_domain': 'mysite.com',
            'use_https': 'yes',
            'opening_bank_balance': '1234.56',
            'accounting_start_date': '2000-01-01',
        })

        opening_balance = Account.objects.get(name='Opening Balance')
        bank = Account.objects.get(name='Bank')
        self.assertEqual(opening_balance.balance(), Balance('1234.56', 'GBP'))
        self.assertEqual(bank.balance(), Balance('1234.56', 'GBP'))

    def test_get_when_already_setup(self):
        Settings.objects.create()
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 302)

    def test_post_when_already_setup(self):
        Settings.objects.create()
        response = self.client.post(self.view_url)
        self.assertEqual(response.status_code, 302)
