from django.core.management.base import BaseCommand

from hordak.models import Account


class Command(BaseCommand):
    help = 'Create the initial chart of accounts'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--preserve', dest='preserve', default=False, action='store_true',
            help='Exit normally if any accounts already exist.',
        )
        parser.add_argument(
            '--currency', dest='currency', default='USD', action='store',
            help='Account currencies.',
        )

    def handle(self, *args, **options):
        if options.get('preserve') and Account.objects.count():
            self.stdout.write('Exiting normally because accounts already exist and --preserve flag was present')

        kw = dict(currencies=[options.get('currency', 'USD')])

        assets = Account.objects.create(name='Assets', code='1', _type='AS', **kw)
        liabilities = Account.objects.create(name='Liabilities', code='1', _type='AS', **kw)
        equity = Account.objects.create(name='Equity', code='1', _type='AS', **kw)
        income = Account.objects.create(name='Income', code='1', _type='AS', **kw)
        expenses = Account.objects.create(name='Expenses', code='1', _type='AS', **kw)

        bank = Account.objects.create(name='Bank', code='1', is_bank_account=True, _type='AS', parent=assets, **kw)

        housemate_income = Account.objects.create(name='Housemate Income', code='1', parent=income, **kw)
        other_income = Account.objects.create(name='Other Income', code='2', parent=income, **kw)

        current_liabilities = Account.objects.create(name='Current Liabilities', code='1', parent=liabilities, **kw)
        long_term_liabilities = Account.objects.create(name='Long Term Liabilities', code='2', parent=liabilities, **kw)

        gas_payable = Account.objects.create(name='Gas Payable', code='1', parent=current_liabilities, **kw)
        electricity_payable = Account.objects.create(name='Electricity Payable', code='2', parent=current_liabilities, **kw)
        council_tax_payable = Account.objects.create(name='Council Tax Payable', code='3', parent=current_liabilities, **kw)
        internet_payable = Account.objects.create(name='Internet Payable', code='4', parent=current_liabilities, **kw)

        retained_earnings = Account.objects.create(name='Retained Earnings', code='1', parent=equity, **kw)

        rent = Account.objects.create(name='Rent', code='1', parent=expenses, **kw)
        utilities = Account.objects.create(name='Utilities', code='2', parent=expenses, **kw)
        food = Account.objects.create(name='Food', code='3', parent=expenses, **kw)
        other_expenses = Account.objects.create(name='Other Expenses', code='4', parent=expenses, **kw)

        gas_expense = Account.objects.create(name='Gas Expense', code='1', parent=utilities, **kw)
        electricity_expense = Account.objects.create(name='Electricity Expense', code='2', parent=utilities, **kw)
        council_tax_expense = Account.objects.create(name='Council Tax Expense', code='3', parent=utilities, **kw)
        internet_expense = Account.objects.create(name='Internet Expense', code='4', parent=utilities, **kw)

