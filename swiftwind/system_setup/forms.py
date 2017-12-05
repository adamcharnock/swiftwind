from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UsernameField
from django.contrib.sites.models import _simple_domain_name_validator, Site
from django.core.exceptions import ValidationError
from djmoney.money import Money
from djmoney.settings import CURRENCY_CHOICES

from hordak.models import Account
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.core.management.commands.swiftwind_create_accounts import Command as SwiftwindCreateAccountsCommand
from swiftwind.settings.models import Settings
from swiftwind.housemates.models import Housemate

User = get_user_model()


class SetupForm(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField()
    username = UsernameField()
    password1 = forms.CharField(label='Password', strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput, strip=False,
                                help_text='Enter the same password as before, for verification.')

    default_currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='EUR')
    additional_currencies = forms.MultipleChoiceField(choices=CURRENCY_CHOICES, widget=forms.SelectMultiple(),
                                                      required=False)
    accounting_start_date = forms.DateField(
        help_text='When should we start accounting from?'
    )
    opening_bank_balance = forms.DecimalField(min_value=0, max_digits=13, decimal_places=2,
                                              initial='0.00',
                                              help_text='Enter your opening bank balance if you are '
                                                        'moving over from an existing accounting system.'
                                                        'Ignore otherwise.')

    site_name = forms.CharField(max_length=50, initial='Swiftwind',
                                help_text='What name shall we display to users of this software?')
    site_domain = forms.CharField(max_length=100, validators=[_simple_domain_name_validator],
                                  help_text='What is the domain name you will use for this site? '
                                            'If unsure leave at the default value.')
    use_https = forms.BooleanField(initial=False, required=False,
                                   help_text='Is this site being served over HTTPS? '
                                             'If unsure leave at the default value.')

    def clean(self):
        if Settings.objects.exists():
            raise ValidationError('Swiftwind has already been setup')

        if self.cleaned_data['password1'] != self.cleaned_data['password2']:
            raise ValidationError('Passwords do not match')

        return super().clean()

    def clean_username(self):
        if User.objects.filter(username=self.cleaned_data['username']).exists():
            raise ValidationError('That username already exists')
        return self.cleaned_data['username']

    def save(self):
        # Create the superuser
        user = User.objects.create(
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data['email'],
            username=self.cleaned_data['username'],
            is_superuser=True,
            is_staff=True,
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()

        # Save the settings
        db_settings = Settings.objects.get()
        db_settings.default_currency = self.cleaned_data['default_currency']
        db_settings.additional_currencies = self.cleaned_data['additional_currencies']
        db_settings.use_https = self.cleaned_data['use_https']
        db_settings.save()

        # Save the site details
        Site.objects.update_or_create(defaults=dict(
            domain=self.cleaned_data['site_domain'],
            name=self.cleaned_data['site_name'],
        ))

        # Create the initial accounts
        if not Account.objects.exists():
            SwiftwindCreateAccountsCommand().handle(
                currency=self.cleaned_data['default_currency'],
            )

        # Create a housemate & account
        account = Account.objects.create(
            name=user.get_full_name() or user.username,
            parent=Account.objects.get(name='Housemate Income'),
            code='00',
            currencies=[self.cleaned_data['default_currency']],
        )
        Housemate.objects.create(
            account=account,
            user=user,
        )

        # Create opening balance account
        if self.cleaned_data['opening_bank_balance']:
            opening_balance_account = Account.objects.create(
                name='Opening Balance',
                code='99',
                currencies=[self.cleaned_data['default_currency']],
                type=Account.TYPES.income,
            )
            opening_balance_account.transfer_to(
                Account.objects.get(name='Bank'),
                amount=Money(self.cleaned_data['opening_bank_balance'], self.cleaned_data['default_currency'])
            )

        # Create the billing cycles
        BillingCycle.populate(as_of=self.cleaned_data['accounting_start_date'])
