from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic.edit import CreateView, UpdateView

from swiftwind.housemates.views import HousematesRequiredMixin
from .forms import RecurringCostFormSet, OneOffCostFormSet, CreateOneOffCostForm, \
    CreateRecurringCostForm
from .models import RecurringCost


class RecurringCostsView(LoginRequiredMixin, HousematesRequiredMixin, UpdateView):
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
        context['disabled_costs'] = RecurringCost.objects.filter(disabled=True).recurring()
        return context

    def get_queryset(self):
        return RecurringCost.objects.filter(total_billing_cycles=None, disabled=False)

    def get_form_kwargs(self):
        kwargs = super(RecurringCostsView, self).get_form_kwargs()
        kwargs.pop('instance')
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_success_url(self):
        return reverse('costs:recurring')


class CreateRecurringCostView(LoginRequiredMixin, HousematesRequiredMixin, CreateView):
    form_class = CreateRecurringCostForm
    template_name = 'costs/create_recurring.html'

    def get_success_url(self):
        return reverse('costs:recurring')


class OneOffCostsView(RecurringCostsView):
    template_name = 'costs/one_off.html'
    form_class = OneOffCostFormSet

    def get_queryset(self):
        return RecurringCost.objects.filter(disabled=False).one_off()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['disabled_costs'] = RecurringCost.objects.filter(disabled=True).one_off()
        return context

    def get_success_url(self):
        return reverse('costs:one_off')


class CreateOneOffCostView(LoginRequiredMixin, HousematesRequiredMixin, CreateView):
    form_class = CreateOneOffCostForm
    template_name = 'costs/create_one_off.html'

    def get_success_url(self):
        return reverse('costs:one_off')
