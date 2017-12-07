from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls.base import reverse_lazy
from django.views.generic.edit import UpdateView

from .models import Settings
from . import forms


class SettingsUpdateView(LoginRequiredMixin, UpdateView):

    def get_object(self, queryset=None):
        return Settings.objects.get()


class GeneralSettingsView(SettingsUpdateView):
    form_class = forms.GeneralSettingsForm
    template_name = 'settings/general.html'
    success_url = reverse_lazy('settings:general')


class TechnicalSettingsView(SettingsUpdateView):
    form_class = forms.TechnicalSettingsForm
    template_name = 'settings/technical.html'
    success_url = reverse_lazy('settings:technical')


class EmailSettingsView(SettingsUpdateView):
    form_class = forms.EmailSettingsForm

    template_name = 'settings/email.html'
    success_url = reverse_lazy('settings:email')


class TellerSettingsView(SettingsUpdateView):
    form_class = forms.TellerSettingsForm
    template_name = 'settings/teller.html'
    success_url = reverse_lazy('settings:teller')
