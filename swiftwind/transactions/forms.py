from django import forms
from django.forms import inlineformset_factory, formset_factory
from hordak.models import Account, Transaction

from swiftwind.transactions.models import TransactionImportColumn, TransactionImport
from swiftwind.utilities.widgets import PlainTextWidget


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


class TransactionImportForm(forms.ModelForm):

    class Meta:
        model = TransactionImport
        fields = ('has_headings', 'file')

    def save(self, commit=True):
        exists = bool(self.instance.pk)
        obj = super(TransactionImportForm, self).save()
        if not exists:
            obj.create_columns()
        return obj


class TransactionImportColumnForm(forms.ModelForm):
    column_number = forms.CharField(widget=forms.HiddenInput, disabled=True)

    class Meta:
        model = TransactionImportColumn
        fields = ('to_field', 'column_number')


TransactionImportFieldFormSet = inlineformset_factory(
    parent_model=TransactionImport,
    model=TransactionImportColumn,
    form=TransactionImportColumnForm,
    extra=0,
    can_delete=False,
)
