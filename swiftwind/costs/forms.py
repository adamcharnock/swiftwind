from django import forms
from django.core.exceptions import ValidationError
from django.utils.datetime_safe import datetime
from hordak.models import Account
from mptt.forms import TreeNodeChoiceField

from swiftwind.billing_cycle.models import BillingCycle
from .models import RecurringCost, RecurringCostSplit
from swiftwind.utilities.formsets import nested_model_formset_factory


class AbstractCostForm(forms.ModelForm):
    to_account = TreeNodeChoiceField(queryset=Account.objects.all(), to_field_name='uuid')
    initial_billing_cycle = forms.ModelChoiceField(queryset=BillingCycle.objects.none(), required=False)

    class Meta:
        model = RecurringCost
        fields = []

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', {})
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'].update(to_account=instance.to_account.uuid)

        super(AbstractCostForm, self).__init__(*args, **kwargs)
        self.fields['initial_billing_cycle'].queryset = self.get_initial_billing_cycle_queryset()

    def get_initial_billing_cycle_queryset(self):
        return BillingCycle.objects.filter(
            end_date__gte=datetime.now().date(),
        )

    def save(self, commit=True):
        creating = not bool(self.instance.pk)
        recurring_cost = super(AbstractCostForm, self).save(commit)

        if creating:
            # TODO: Make configurable
            housemate_accounts = Account.objects.get(name='Housemate Income').get_children()
            for housemate_account in housemate_accounts:
                RecurringCostSplit.objects.create(
                    recurring_cost=recurring_cost,
                    from_account=housemate_account,
                )

        return recurring_cost

    def clean_initial_billing_cycle(self):
        value = self.cleaned_data.get('initial_billing_cycle')
        if value and self.cleaned_data.get('disabled'):
            raise ValidationError('Cannot specify initial billing cycle for a disabled cost')

        if not value and not self.cleaned_data.get('disabled'):
            raise ValidationError('Active costs require an initial billing cycle')

        return value


class RecurringCostForm(AbstractCostForm):
    type = forms.ChoiceField(choices=RecurringCost.TYPES, widget=forms.RadioSelect)

    class Meta(AbstractCostForm.Meta):
        fields = ('to_account', 'type', 'disabled', 'fixed_amount', 'initial_billing_cycle')
        labels = dict(
            disabled='Disable this recurring cost',
        )

    def clean_fixed_amount(self):
        value = self.cleaned_data['fixed_amount']
        if value and self.cleaned_data['type'] != RecurringCost.TYPES.normal:
            raise ValidationError('You cannot specify a fixed amount for the selected type of recurring cost')
        return value


class OneOffCostForm(AbstractCostForm):
    fixed_amount = forms.DecimalField(required=True, label='Amount')
    total_billing_cycles = forms.IntegerField(required=True, label='Total Billing Cycles', initial=1)

    class Meta(AbstractCostForm.Meta):
        fields = ('to_account', 'fixed_amount', 'total_billing_cycles', 'initial_billing_cycle')

    def save(self, commit=True):
        self.instance.type = RecurringCost.TYPES.normal
        return super(OneOffCostForm, self).save(commit)


class RecurringCostSplitForm(forms.ModelForm):

    class Meta:
        model = RecurringCostSplit
        fields = ('portion', )


RecurringCostFormSet = nested_model_formset_factory(
    model=RecurringCost,
    form=RecurringCostForm,
    extra=0,
    can_delete=False,
    nested_formset=forms.inlineformset_factory(
        parent_model=RecurringCost,
        model=RecurringCostSplit,
        form=RecurringCostSplitForm,
        extra=0,
        can_delete=False,
    )
)


OneOffCostFormSet = nested_model_formset_factory(
    model=RecurringCost,
    form=OneOffCostForm,
    extra=0,
    can_delete=False,
    nested_formset=forms.inlineformset_factory(
        parent_model=RecurringCost,
        model=RecurringCostSplit,
        form=RecurringCostSplitForm,
        extra=0,
        can_delete=False,
    )
)


RecurringCostSplitFormSet = forms.inlineformset_factory(
    parent_model=RecurringCost,
    model=RecurringCostSplit,
    form=RecurringCostSplitForm,
    extra=0,
    can_delete=False,
)
