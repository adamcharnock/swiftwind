from hordak.models.core import Account
from hordak.tests.utils import DataProvider as HordakDataProvider
from swiftwind.housemates.models import Housemate


class DataProvider(HordakDataProvider):

    def housemate(self, user=None, account=None):
        try:
            housemate_income = Account.objects.get(name='Housemate Income')
        except Account.DoesNotExist:
            housemate_income = None

        return Housemate.objects.create(
            user=user or self.user(),
            account=account or self.account(type=Account.TYPES.income, parent=housemate_income),
        )
