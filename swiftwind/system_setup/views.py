from django.contrib.auth import authenticate, login
from django.db import transaction
from django.http.response import HttpResponseRedirect
from django.urls.base import reverse_lazy, reverse
from django.views.generic import FormView

from swiftwind.core.models import Settings
from swiftwind.system_setup.forms import SetupForm


class SetupView(FormView):
    template_name = 'setup/index.html'
    form_class = SetupForm
    success_url = reverse_lazy('dashboard:dashboard')

    def dispatch(self, request, *args, **kwargs):
        if Settings.objects.exists():
            return HttpResponseRedirect(reverse('dashboard:dashboard'))
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super(SetupView, self).get_initial()
        port = self.request.get_port()
        domain = self.request.get_host()
        if port != '80' and ':' not in domain:
            domain = '{}:{}'.format(domain, port)

        initial.update(
            site_domain=domain,
            use_https=self.request.is_secure(),
        )
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            form.save()

        # Now login as the newly created user
        user = authenticate(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password1']
        )
        login(self.request, user)
        return super().form_valid(form)
