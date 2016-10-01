from django.db import transaction as db_transaction
from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from swiftwind.costs_recurring.forms import RecurringCostForm, RecurringCostSplitForm, RecurringCostSplitFormSet
from swiftwind.costs_recurring.models import RecurringCost


class RecurringCostsView(ListView):
    template_name = 'costs_recurring/list.html'
    model = RecurringCost
    context_object_name = 'recurring_costs'
    ordering = ['is_active', 'to_account__name']

    def get_object(self):
        uuid = self.request.POST.get('uuid')
        if not uuid:
            return None

        try:
            obj = RecurringCost.objects.get(uuid=uuid)
        except RecurringCost.DoesNotExist:
            obj = None

        return obj

    def get(self, request, *args, **kwargs):
        self.object = None
        return super(RecurringCostsView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.request = request
        self.object = self.get_object()

        # Make sure the ListView gets setup
        self.get(self.request, *self.args, **self.kwargs)

        # Check form validity
        cost_form = self.get_cost_form(self.object)
        cost_split_formset = self.get_cost_split_formset(self.object)

        if cost_form.is_valid() and cost_split_formset.is_valid():
            return self.form_valid(cost_form, cost_split_formset)
        else:
            return self.form_invalid(cost_form, cost_split_formset)

    def form_valid(self, cost_form, cost_split_formset):
        with db_transaction.atomic():
            cost_form.save()
            cost_split_formset.save()

        self.object = None
        return self.render_to_response(self.get_context_data())

    def form_invalid(self):
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        kwargs.update(
            form_list=[
                (self.get_cost_form(inst), self.get_cost_split_formset(inst))
                for inst
                in self.object_list
            ],
        )
        return super(RecurringCostsView, self).get_context_data(**kwargs)

    def get_cost_form(self, instance):
        being_edited = (instance == self.object)
        data = self.request.POST if being_edited else None

        return RecurringCostForm(data=data, instance=instance)

    def get_cost_split_formset(self, instance):
        being_edited = (instance == self.object)
        data = self.request.POST if being_edited else None

        return RecurringCostSplitFormSet(data=data, instance=instance)


class CreateRecurringCostView(CreateView):
    form_class = RecurringCostForm
    template_name = 'costs_recurring/create.html'
    # model = RecurringCost

    def get_success_url(self):
        return reverse('costs_recurring:list')
