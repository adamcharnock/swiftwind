from django import forms
from django.core.exceptions import ValidationError
from hordak.models import Account
from mptt.forms import TreeNodeChoiceField

from .models import RecurringCost, RecurringCostSplit
from swiftwind.utilities.formsets import nested_model_formset_factory


class AbstractCostForm(forms.ModelForm):
    to_account = forms.ModelChoiceField(queryset=Account.objects.all(), to_field_name='uuid')

    class Meta:
        model = RecurringCost
        fields = []

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', {})
        instance = kwargs.get('instance')
        if instance:
            kwargs['initial'].update(to_account=instance.to_account.uuid)

        super(AbstractCostForm, self).__init__(*args, **kwargs)

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


class RecurringCostForm(AbstractCostForm):
    type = forms.ChoiceField(choices=RecurringCost.TYPES, widget=forms.RadioSelect)

    class Meta(AbstractCostForm.Meta):
        fields = ('to_account', 'type', 'is_active', 'fixed_amount')
        labels = dict(
            is_active='Enable this recurring cost',
        )

    def clean_fixed_amount(self):
        value = self.cleaned_data['fixed_amount']
        if value and self.cleaned_data['type'] != RecurringCost.TYPES.normal:
            raise ValidationError('You cannot specify a fixed amount for the select type of recurring cost')
        return value


class OneOffCostForm(AbstractCostForm):
    fixed_amount = forms.DecimalField(required=True, label='Amount')
    total_billing_cycles = forms.IntegerField(required=True, label='Total Billing Cycles', initial=1)

    class Meta(AbstractCostForm.Meta):
        fields = ('to_account', 'fixed_amount', 'total_billing_cycles')

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
