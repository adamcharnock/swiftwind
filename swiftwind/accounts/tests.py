from django.test import TestCase

from swiftwind.accounts.views import StatementEmailView
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.utilities.testing import DataProvider


class StatementEmailViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.login()

    def test_get_html(self):
        housemate = self.housemate()
        billing_cycle = BillingCycle.objects.create(
            date_range=['2000-01-01', '2000-02-01'],
        )
        billing_cycle.refresh_from_db()
        html = StatementEmailView.get_html(uuid=housemate.uuid, date='2000-01-01')
        self.assertIn('<html>', html)
