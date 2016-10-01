from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView

from .forms import RecurringCostForm, RecurringCostFormSet, OneOffCostFormSet, OneOffCostForm
from .models import RecurringCost


class RecurringCostsView(UpdateView):
    template_name = 'costs/recurring.html'
    model = RecurringCost
    ordering = ['is_active', 'to_account__name']
    form_class = RecurringCostFormSet

    def get_object(self, queryset=None):
        return None

    def get_context_data(self, **kwargs):
        context = super(RecurringCostsView, self).get_context_data(**kwargs)
        context['formset'] = context['form']
        context['form_action'] = self.get_success_url()
        return context

    def get_queryset(self):
        return RecurringCost.objects.filter(total_billing_cycles=None)

    def get_form_kwargs(self):
        kwargs = super(RecurringCostsView, self).get_form_kwargs()
        kwargs.pop('instance')
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_success_url(self):
        return reverse('costs:recurring')


class CreateRecurringCostView(CreateView):
    form_class = RecurringCostForm
    template_name = 'costs/create_recurring.html'

    def get_success_url(self):
        return reverse('costs:recurring')


class OneOffCostsView(RecurringCostsView):
    template_name = 'costs/one_off.html'
    form_class = OneOffCostFormSet

    def get_queryset(self):
        return RecurringCost.objects.exclude(total_billing_cycles=None)

    def get_success_url(self):
        return reverse('costs:one_off')


class CreateOneOffCostView(CreateView):
    form_class = OneOffCostForm
    template_name = 'costs/create_one_off.html'

    def get_success_url(self):
        return reverse('costs:one_off')
