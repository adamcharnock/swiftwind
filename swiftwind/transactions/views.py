from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views import View
from django.views.generic.edit import CreateView, SingleObjectMixin, UpdateView
from hordak.models import Transaction

from swiftwind.transactions.models import TransactionImport, TransactionImportColumn
from .forms import SimpleTransactionForm, TransactionImportForm, TransactionImportColumnFormSet


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


class SetupImportView(UpdateView):
    """View for setting up of the import process

    This involves mapping columns to import fields, and collecting
    the date format
    """
    context_object_name = 'transaction_import'
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = TransactionImport
    fields = ('date_format', )
    template_name = 'transactions/setup_import.html'

    def get_context_data(self, **kwargs):
        context = super(SetupImportView, self).get_context_data(**kwargs)
        context['formset'] = TransactionImportColumnFormSet(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form_class()(request.POST, request.FILES, instance=self.object)
        formset = TransactionImportColumnFormSet(request.POST, instance=self.object)

        if form.is_valid() and formset.is_valid():
            return self.form_valid(form, formset)
        else:
            return self.form_invalid(form, formset)

    def form_valid(self, form, formset):
        self.object = form.save()
        formset.instance = self.object
        formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, formset):
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def get_success_url(self):
        return reverse('transactions:import_dry_run', args=[self.object.uuid])


class DryRunImportView(View):
    pass
