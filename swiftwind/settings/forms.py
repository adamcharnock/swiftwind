from django import forms
from django.contrib.sites.models import _simple_domain_name_validator, Site
from djmoney.settings import CURRENCY_CHOICES

from swiftwind.settings.models import Settings


class GeneralSettingsForm(forms.ModelForm):
    default_currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='EUR')
    additional_currencies = forms.MultipleChoiceField(choices=CURRENCY_CHOICES, widget=forms.SelectMultiple(),
                                                      required=False)

    class Meta:
        model = Settings
        fields = [
            'default_currency',
            'additional_currencies',
            'payment_information',
        ]


class TechnicalSettingsForm(forms.ModelForm):
    site_name = forms.CharField(max_length=50, initial='Swiftwind',
                                help_text='What name shall we display to users of this software?')
    site_domain = forms.CharField(max_length=100, validators=[_simple_domain_name_validator],
                                  help_text='What is the domain name you use for this site?')
    use_https = forms.BooleanField(initial=False, required=False,
                                   help_text='Is this site being served over HTTPS?')

    class Meta:
        model = Settings
        fields = [
            'use_https',
        ]

    def __init__(self, *args, **kwargs):
        self.site = Site.objects.get()
        initial = kwargs.get('initial') or {}
        initial.setdefault('site_name', self.site.name)
        initial.setdefault('site_domain', self.site.domain)
        kwargs.update(initial=initial)

        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=commit)
        self.site.name = self.cleaned_data['site_name']
        self.site.domain = self.cleaned_data['site_domain']
        self.site.save()
        return obj


class EmailSettingsForm(forms.ModelForm):
    smtp_host = forms.CharField(required=True, label='SMTP host')
    smtp_port = forms.IntegerField(required=True, label='SMTP port')
    smtp_user = forms.CharField(label='SMTP user')
    smtp_password = forms.CharField(widget=forms.PasswordInput(render_value=True), label='SMTP password')
    smtp_use_ssl = forms.BooleanField(initial=True, label='Use SSL')

    class Meta:
        model = Settings
        fields = [
            'smtp_host',
            'smtp_port',
            'smtp_user',
            'smtp_password',
            'smtp_use_ssl',
        ]


class TellerSettingsForm(forms.ModelForm):
    tellerio_token = forms.CharField(max_length=100, widget=forms.PasswordInput)

    class Meta:
        model = Settings
        fields = [
            'tellerio_token',
            'tellerio_account_id',
            'tellerio_enable',
        ]
