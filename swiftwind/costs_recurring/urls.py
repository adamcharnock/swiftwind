from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^recurring/$', views.RecurringCostsView.as_view(), name='recurring'),
    url(r'^oneoff/$', views.OneOffCostsView.as_view(), name='one_off'),
    url(r'^recurring/create/$', views.CreateRecurringCostView.as_view(), name='create_recurring'),
    url(r'^oneoff/create/$', views.CreateOneOffCostView.as_view(), name='create_one_off'),
]
