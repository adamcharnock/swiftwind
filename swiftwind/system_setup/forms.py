import hmac

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import ValidationError
from djmoney.settings import CURRENCY_CHOICES

from hordak.models import Account
from swiftwind.billing_cycle.models import BillingCycle
from swiftwind.core.management.commands.swiftwind_create_accounts import Command as SwiftwindCreateAccountsCommand
from swiftwind.core.models import Settings
from swiftwind.housemates.models import Housemate

User = get_user_model()


class SetupForm(forms.Form):
    email = forms.EmailField()
    username = UsernameField()
    password1 = forms.CharField(label='Password', strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput, strip=False,
                                help_text='Enter the same password as before, for verification.')

    default_currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='EUR')
    additional_currencies = forms.MultipleChoiceField(choices=CURRENCY_CHOICES, widget=forms.SelectMultiple(),
                                                      required=False)

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
        db_settings.save()

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

        # Create the billing cycles
        BillingCycle.populate()
