from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from swiftwind.billing_cycle.models import BillingCycle


class BillingCycleListView(LoginRequiredMixin, ListView):
    template_name = 'billing_cycle/list.html'
    context_object_name = 'billing_cycles'

    def get_queryset(self):
        return BillingCycle.objects.filter(
            start_date__lte=date.today()
        ).order_by('-date_range')


class CreateTransactionsView(LoginRequiredMixin, View):

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        if billing_cycle.can_create_transactions():
            billing_cycle.enact_all_costs()
        return HttpResponseRedirect(reverse('billing_cycles:list'))


class RecreateTransactionsView(LoginRequiredMixin, View):
    """For those times when you realise you're costs were not setup correctly"""

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        billing_cycle.reenact_all_costs()
        return HttpResponseRedirect(reverse('billing_cycles:list'))


class DeleteTransactionsView(LoginRequiredMixin, View):
    """For those times when you need to delete the transactions and faff about some more"""

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        billing_cycle.unenact_all_costs()
        return HttpResponseRedirect(reverse('billing_cycles:list'))


class SendNotificationsView(LoginRequiredMixin, View):

    def post(self, request, uuid):
        billing_cycle = get_object_or_404(BillingCycle, uuid=uuid)
        if billing_cycle.can_send_statements():
            billing_cycle.send_statements(force=True)
        return HttpResponseRedirect(reverse('billing_cycles:list'))

