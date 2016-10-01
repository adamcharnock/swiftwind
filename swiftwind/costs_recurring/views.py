from django.db import transaction as db_transaction
from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from swiftwind.costs_recurring.forms import RecurringCostForm, RecurringCostSplitForm, RecurringCostSplitFormSet, \
    RecurringCostFormSet
from swiftwind.costs_recurring.models import RecurringCost


class RecurringCostsView(ListView):
    template_name = 'costs_recurring/list.html'
    model = RecurringCost
    context_object_name = 'recurring_costs'
    ordering = ['is_active', 'to_account__name']

    def post(self, request, *args, **kwargs):
        # Make sure the ListView gets setup
        self.get(self.request, *self.args, **self.kwargs)

        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with db_transaction.atomic():
            formset.save()

        return self.render_to_response(self.get_context_data())

    def form_invalid(self, formset):
        return self.render_to_response(self.get_context_data(formset=formset))

    def get_context_data(self, formset=None, **kwargs):
        formset = formset or self.get_formset()
        return super(RecurringCostsView, self).get_context_data(formset=formset, **kwargs)

    def get_formset(self, **kwargs):
        return RecurringCostFormSet(queryset=RecurringCost.objects.all(), **kwargs)


class CreateRecurringCostView(CreateView):
    form_class = RecurringCostForm
    template_name = 'costs_recurring/create.html'
    # model = RecurringCost

    def get_success_url(self):
        return reverse('costs_recurring:list')
