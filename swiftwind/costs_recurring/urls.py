from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', views.RecurringCostsView.as_view(), name='list'),
    url(r'^create/$', views.CreateRecurringCostView.as_view(), name='create'),
]
