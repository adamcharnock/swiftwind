from django.shortcuts import render

# Create your views here.
from django.views.generic.edit import FormView


class SetupView(FormView):
    template_name = 'setup/index.html'
