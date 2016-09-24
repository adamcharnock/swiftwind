from hordak.models import Transaction
from import_export import resources


class TransactionResource(resources.ModelResource):

    class Meta:
        model = Transaction


