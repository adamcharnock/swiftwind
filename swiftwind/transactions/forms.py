from django import forms
from hordak.models import Account, Transaction


class SimpleTransactionForm(forms.ModelForm):
    from_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    to_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    amount = forms.DecimalField(decimal_places=2)

    class Meta:
        model = Transaction
        fields = ['description', ]

    def save(self, commit=True):
        from_account = self.cleaned_data.get('from_account')
        to_account = self.cleaned_data.get('to_account')
        amount = self.cleaned_data.get('amount')

        return from_account.transfer_to(
            to_account=to_account,
            amount=amount,
            description=self.cleaned_data.get('description')
        )
