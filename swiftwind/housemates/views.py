from django.urls import reverse
from django.views.generic import CreateView
from django.views.generic import UpdateView
from django.views.generic.list import ListView

from swiftwind.housemates.forms import HousemateUpdateForm
from .forms import HousemateCreateForm
from .models import Housemate


class HousemateListView(ListView):
    template_name = 'housemates/list.html'
    context_object_name = 'housemates'
    queryset = Housemate.objects.all()\
        .order_by('user__is_active', 'user__first_name', 'user__last_name')\
        .select_related('user', 'account')


class HousemateCreateView(CreateView):
    template_name = 'housemates/create.html'
    form_class = HousemateCreateForm

    def get_success_url(self):
        return reverse('housemates:list')


class HousemateUpdateView(UpdateView):
    template_name = 'housemates/update.html'
    form_class = HousemateUpdateForm
    model = Housemate
    slug_url_kwarg = 'uuid'
    slug_field = 'uuid'
    context_object_name = 'housemate'

    def get_success_url(self):
        return reverse('housemates:list')
