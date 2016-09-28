from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, SingleObjectMixin, UpdateView, FormMixin
from django.views.generic.list import ListView
from hordak.models import Transaction, StatementLine, Leg
from django.http import Http404
from django.db import transaction as db_transaction

from swiftwind.transactions.forms import TransactionForm, LegFormSet
from swiftwind.transactions.models import TransactionImport, TransactionImportColumn
from swiftwind.transactions.resources import StatementLineResource
from .forms import SimpleTransactionForm, TransactionImportForm, TransactionImportColumnFormSet


class CreateTransactionView(CreateView):
    form_class = SimpleTransactionForm
    template_name = 'transactions/transaction_create.html'

    def get_success_url(self):
        return reverse('dashboard:dashboard')


class CreateImportView(CreateView):
    model = TransactionImport
    form_class = TransactionImportForm
    template_name = 'transactions/import_create.html'

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
    template_name = 'transactions/import_setup.html'

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


class AbstractImportView(DetailView):
    context_object_name = 'transaction_import'
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    model = TransactionImport
    dry_run = True

    def get(self, request, **kwargs):
        return super(AbstractImportView, self).get(request, **kwargs)

    def post(self, request, **kwargs):
        transaction_import = self.get_object()
        resource = StatementLineResource(
            date_format=transaction_import.date_format,
            statement_import=transaction_import.hordak_import,
        )

        self.result = resource.import_data(
            dataset=transaction_import.get_dataset(),
            dry_run=self.dry_run,
            use_transactions=True,
            collect_failed_rows=True,
        )
        return self.get(request, **kwargs)

    def get_context_data(self, **kwargs):
        return super(AbstractImportView, self).get_context_data(
            result=getattr(self, 'result', None),
            **kwargs
        )


class DryRunImportView(AbstractImportView):
    template_name = 'transactions/import_dry_run.html'
    dry_run = True


class ExecuteImportView(AbstractImportView):
    template_name = 'transactions/import_execute.html'
    dry_run = False


class ReconcileTransactionsView(ListView):
    """ Handle rendering and processing in the reconciliation view

    Note that this only extends ListView, and we implement the form
    processing functionality manually.
    """
    template_name = 'transactions/reconcile.html'
    model = StatementLine
    paginate_by = 50
    context_object_name = 'statement_lines'
    ordering = ['-date', '-pk']

    def get_uuid(self):
        return self.request.POST.get('reconcile') or self.request.GET.get('reconcile')

    def get_object(self, queryset=None):
        # Get any Statement Line instance that was specified
        if queryset is None:
            queryset = self.get_queryset()

        uuid = self.get_uuid()
        if not uuid:
            return None

        queryset = queryset.filter(uuid=uuid, transaction=None)
        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404('No unreconciled statement line found for {}'.format(uuid))

        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(ReconcileTransactionsView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Make sure the ListView gets setup
        self.get(self.request, *self.args, **self.kwargs)

        # Check form validity
        transaction_form = self.get_transaction_form()
        leg_formset = self.get_leg_formset()

        if transaction_form.is_valid() and leg_formset.is_valid():
            return self.form_valid(transaction_form, leg_formset)
        else:
            return self.form_invalid(transaction_form, leg_formset)

    def form_valid(self, transaction_form, leg_formset):

        with db_transaction.atomic():
            # Save the transaction
            transaction = transaction_form.save()

            # Create the inbound transaction leg
            bank_account = self.object.statement_import.bank_account
            amount = self.object.amount * -1
            Leg.objects.create(transaction=transaction, account=bank_account, amount=amount)

            # We need to create a new leg formset in order to pass in the
            # transaction we just created (required as the new legs must
            # be associated with the new transaction)
            leg_formset = self.get_leg_formset(instance=transaction)
            assert leg_formset.is_valid()
            leg_formset.save()

            # Now point the statement line to the new transaction
            self.object.transaction = transaction
            self.object.save()

        self.object = None
        return self.render_to_response(self.get_context_data())

    def form_invalid(self, transaction_form, leg_formset):
        return self.render_to_response(self.get_context_data(
            transaction_form=transaction_form,
            leg_formset=leg_formset
        ))

    def get_context_data(self, **kwargs):
        # If a Statement Line has been selected for reconciliation,
        # then add the forms to the context
        if self.object:
            kwargs.update(
                transaction_form=self.get_transaction_form(),
                leg_formset=self.get_leg_formset(),
                reconcile_line=self.object,
            )
        return super(ReconcileTransactionsView, self).get_context_data(**kwargs)

    def get_transaction_form(self):
        return TransactionForm(
            data=self.request.POST or None,
            initial=dict(description=self.object.description)
        )

    def get_leg_formset(self, **kwargs):
        return LegFormSet(data=self.request.POST or None, statement_line=self.object, **kwargs)
