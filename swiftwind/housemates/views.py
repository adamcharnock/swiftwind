from django.shortcuts import render
from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic.list import ListView

from .forms import HousemateForm
from .models import Housemate


class HousemateListView(ListView):
    template_name = 'housemates/list.html'
    context_object_name = 'housemates'
    queryset = Housemate.objects.all()\
        .order_by('user__is_active', 'user__first_name', 'user__last_name')\
        .select_related('user', 'account')


class HousemateCreateView(CreateView):
    template_name = 'housemates/create.html'
    form_class = HousemateForm

    def get_success_url(self):
        return reverse('housemates:list')
