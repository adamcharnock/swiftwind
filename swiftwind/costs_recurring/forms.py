from django import forms
from django.core.exceptions import ValidationError
from hordak.models import Account
from mptt.forms import TreeNodeChoiceField

from swiftwind.costs_recurring.models import RecurringCost, RecurringCostSplit


class RecurringCostForm(forms.ModelForm):
    to_account = forms.ModelChoiceField(queryset=Account.objects.all(), to_field_name='uuid')

    class Meta:
        model = RecurringCost
        fields = ('to_account', 'type', 'is_active', 'fixed_amount', 'total_billing_cycles')

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', {})
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'].update(to_account=instance.to_account.uuid)

        super(RecurringCostForm, self).__init__(*args, **kwargs)

    def clean_fixed_amount(self):
        value = self.cleaned_data['fixed_amount']
        if value and self.cleaned_data['type'] != RecurringCost.TYPES.normal:
            raise ValidationError('You cannot specify a fixed amount for the select type of recurring cost')
        return value

    def save(self, commit=True):
        creating = not bool(self.instance.pk)
        recurring_cost = super(RecurringCostForm, self).save(commit)

        if creating:
            # TODO: Make configurable
            housemate_accounts = Account.objects.get(name='Housemate Income').get_children()
            for housemate_account in housemate_accounts:
                RecurringCostSplit.objects.create(
                    recurring_cost=recurring_cost,
                    from_account=housemate_account,
                )

        return recurring_cost


class RecurringCostSplitForm(forms.ModelForm):

    class Meta:
        model = RecurringCostSplit
        fields = ('portion', )


RecurringCostSplitFormSet = forms.inlineformset_factory(
    parent_model=RecurringCost,
    model=RecurringCostSplit,
    form=RecurringCostSplitForm,
    extra=0,
    can_delete=False,
)
