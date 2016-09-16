from django.shortcuts import render
from django.urls import reverse
from django.views.generic.edit import CreateView
from hordak.models import Transaction

from .forms import SimpleTransactionForm


class CreateTransactionView(CreateView):
    form_class = SimpleTransactionForm
    template_name = 'transactions/create_transaction.html'

    def get_success_url(self):
        return reverse('dashboard:dashboard')
