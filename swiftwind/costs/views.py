from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

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


class DeleteRecurringCostView(LoginRequiredMixin, HousematesRequiredMixin, DeleteView):
    model = RecurringCost
    success_url = reverse_lazy('costs:recurring')
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    template_name = 'costs/delete_recurring.html'
    queryset = RecurringCost.objects.recurring()
    archive_url_name = 'costs:archive_recurring'

    def archive_url(self):
        return reverse(self.archive_url_name, args=[self.get_object().uuid])

    def get(self, request, *args, **kwargs):
        if self.get_object().can_delete():
            return super().get(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(self.archive_url())

    def delete(self, request, *args, **kwargs):
        if self.get_object().can_delete():
            with transaction.atomic():
                return super().delete(request, *args, **kwargs)
        else:
            return HttpResponseRedirect(self.archive_url())


class DeleteOneOffCostView(DeleteRecurringCostView):
    success_url = reverse_lazy('costs:one_off')
    template_name = 'costs/delete_oneoff.html'
    queryset = RecurringCost.objects.one_off()
    archive_url_name = 'costs:archive_one_off'


class ArchiveRecurringCostView(LoginRequiredMixin, HousematesRequiredMixin, DetailView):
    model = RecurringCost
    success_url = reverse_lazy('costs:recurring')
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    queryset = RecurringCost.objects.recurring()

    def get(self, request, *args, **kwargs):
        # No get requests allowed (as we don't ask for confirmation upon archiving)
        return HttpResponseRedirect(self.success_url)

    def post(self, request, *args, **kwargs):
        self.get_object().archive()
        return HttpResponseRedirect(self.success_url)


class ArchiveOneOffCostView(ArchiveRecurringCostView):
    success_url = reverse_lazy('costs:one_off')
    queryset = RecurringCost.objects.one_off()


class UnarchiveRecurringCostView(LoginRequiredMixin, HousematesRequiredMixin, DetailView):
    model = RecurringCost
    success_url = reverse_lazy('costs:recurring')
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    queryset = RecurringCost.objects.recurring()

    def get(self, request, *args, **kwargs):
        # No get requests allowed (as we don't ask for confirmation upon archiving)
        return HttpResponseRedirect(self.success_url)

    def post(self, request, *args, **kwargs):
        self.get_object().unarchive()
        return HttpResponseRedirect(self.success_url)


class UnarchiveOneOffCostView(UnarchiveRecurringCostView):
    success_url = reverse_lazy('costs:one_off')
    queryset = RecurringCost.objects.one_off()
