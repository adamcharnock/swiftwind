from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, formset_factory, BaseModelFormSet, BaseInlineFormSet
from hordak.models import Account, Transaction, StatementImport, Leg
from mptt.forms import TreeNodeChoiceField

from .models import TransactionImportColumn, TransactionImport
from .utilities import DATE_FORMATS


class SimpleTransactionForm(forms.ModelForm):
    from_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    to_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    amount = forms.DecimalField(decimal_places=2)

    class Meta:
        model = Transaction
        fields = ['amount', 'from_account', 'to_account', 'description', ]

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
    bank_account = forms.ModelChoiceField(Account.objects.filter(has_statements=True), label='Import data for account')

    class Meta:
        model = TransactionImport
        fields = ('has_headings', 'file')

    def save(self, commit=True):
        exists = bool(self.instance.pk)
        self.instance.hordak_import = StatementImport.objects.create(
            bank_account=self.cleaned_data['bank_account'],
        )
        obj = super(TransactionImportForm, self).save()
        if not exists:
            obj.create_columns()
        return obj


class TransactionImportColumnForm(forms.ModelForm):

    class Meta:
        model = TransactionImportColumn
        fields = ('to_field',)


TransactionImportColumnFormSet = inlineformset_factory(
    parent_model=TransactionImport,
    model=TransactionImportColumn,
    form=TransactionImportColumnForm,
    extra=0,
    can_delete=False,
)


class TransactionForm(forms.ModelForm):
    description = forms.CharField(label='Transaction notes', required=False)

    class Meta:
        model = Transaction
        fields = ('description', )

    def save(self, commit=True):
        return super(TransactionForm, self).save(commit)


class LegForm(forms.ModelForm):
    account = TreeNodeChoiceField(Account.objects.all(), to_field_name='uuid')
    description = forms.CharField(required=False)

    class Meta:
        model = Leg
        fields = ('amount', 'account', 'description')


class BaseLegFormSet(BaseInlineFormSet):

    def __init__(self, **kwargs):
        self.statement_line = kwargs.pop('statement_line')
        super(BaseLegFormSet, self).__init__(**kwargs)

    def clean(self):
        super(BaseLegFormSet, self).clean()

        if any(self.errors):
            return

        amounts = [f.cleaned_data['amount'] for f in self.forms if f.has_changed()]
        if self.statement_line.amount != sum(amounts):
            raise ValidationError('Amounts must add up to {}'.format(self.statement_line.amount))


LegFormSet = inlineformset_factory(
    parent_model=Transaction,
    model=Leg,
    form=LegForm,
    extra=2,
    can_delete=False,
    formset=BaseLegFormSet,
)
