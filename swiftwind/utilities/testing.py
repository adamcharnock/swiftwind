from hordak.tests.utils import DataProvider as HordakDataProvider
from swiftwind.housemates.models import Housemate


class DataProvider(HordakDataProvider):

    def housemate(self, user=None, account=None):
        return Housemate.objects.create(
            user=user or self.user(),
            account=account or self.account()
        )
