from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic.edit import CreateView, SingleObjectMixin, UpdateView
from hordak.models import Transaction

from swiftwind.transactions.models import TransactionImport, TransactionImportColumn
from .forms import SimpleTransactionForm, TransactionImportForm, TransactionImportFieldFormSet


class CreateTransactionView(CreateView):
    form_class = SimpleTransactionForm
    template_name = 'transactions/create_transaction.html'

    def get_success_url(self):
        return reverse('dashboard:dashboard')


class CreateImportView(CreateView):
    model = TransactionImport
    form_class = TransactionImportForm
    template_name = 'transactions/create_import.html'

    def get_success_url(self):
        return reverse('transactions:import_setup', args=[self.object.uuid])


class SetupImportView(UpdateView, SingleObjectMixin):
    context_object_name = 'transaction_import'
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = TransactionImport

    form_class = TransactionImportFieldFormSet
    template_name = 'transactions/setup_import.html'

    def form_valid(self, form):
        # We'll need this to create eh success url, as it'll
        # be replaced with a list of our new TransactionImportColumn objects
        self.transaction_import = self.object
        return super(SetupImportView, self).form_valid(form)

    def get_success_url(self):
        return reverse('transactions:import_dry_run', args=[self.transaction_import.uuid])


class DryRunImportView(View):
    pass
