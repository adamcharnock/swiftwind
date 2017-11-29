from django.contrib.auth import authenticate, login
from django.urls.base import reverse_lazy
from django.views.generic import FormView

from swiftwind.system_setup.forms import SetupForm


class SetupView(FormView):
    template_name = 'setup/index.html'
    form_class = SetupForm
    success_url = reverse_lazy('dashboard:dashboard')

    def form_valid(self, form):
        form.save()

        # Now login as the newly created user
        user = authenticate(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password1']
        )
        login(self.request, user)
        return super().form_valid(form)
