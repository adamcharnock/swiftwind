from datetime import date, timedelta

from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from swiftwind.billing_cycle.models import BillingCycle


class BillingCycleListView(ListView):
    template_name = 'billing_cycle/list.html'
    context_object_name = 'billing_cycles'

    def get_queryset(self):
        return BillingCycle.objects.filter(
            start_date__lte=date.today()
        ).order_by('-date_range')


class CreateTransactionsView(View):

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        billing_cycle.enact_all_costs()
        return HttpResponseRedirect(reverse('billing_cycles:list'))


class RecreateTransactionsView(View):
    """For those times when you realise you're costs were not setup correctly"""

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        billing_cycle.reenact_all_costs()
        return HttpResponseRedirect(reverse('billing_cycles:list'))


class SendNotificationsView(View):

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        if billing_cycle.transactions_created:
            billing_cycle.send_statements(force=True)
        return HttpResponseRedirect(reverse('billing_cycles:list'))

