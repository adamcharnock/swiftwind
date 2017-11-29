from django import forms
from django.contrib.auth.forms import UsernameField
from djmoney.settings import CURRENCY_CHOICES

from swiftwind.core.models import Settings


class SetupForm(forms.Form):
    email = forms.EmailField()
    username = UsernameField()
    password1 = forms.CharField(label='Password', strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput, strip=False,
                                help_text='Enter the same password as before, for verification.')

    default_currency = forms.ChoiceField(choices=CURRENCY_CHOICES)
    additional_currencies = forms.MultipleChoiceField(choices=CURRENCY_CHOICES, widget=forms.CheckboxSelectMultiple())

    def save(self):
        db_settings = Settings.objects.get()
        db_settings.default_currency = self.cleaned_data['default_currency']
        db_settings.additional_currencies = self.cleaned_data['additional_currencies']
