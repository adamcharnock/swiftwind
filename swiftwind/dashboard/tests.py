from django.test import TestCase
from django.urls import reverse

from swiftwind.core.management.commands.swiftwind_create_accounts import Command
from swiftwind.utilities.testing import DataProvider


class DashboardViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.url = reverse('dashboard:dashboard')
        Command().handle(currency='GBP')

    def test_get(self):
        self.login()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
