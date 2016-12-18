import hordak.views.transactions
from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', hordak.views.transactions.CreateTransactionView.as_view(), name='create'),
    url(r'^reconcile/$', hordak.views.transactions.ReconcileTransactionsView.as_view(), name='reconcile'),
    url(r'^import/$', views.CreateImportView.as_view(), name='import_create'),
    url(r'^import/(?P<uuid>.*)/setup/$', views.SetupImportView.as_view(), name='import_setup'),
    url(r'^import/(?P<uuid>.*)/dry-run/$', views.DryRunImportView.as_view(), name='import_dry_run'),
    url(r'^import/(?P<uuid>.*)/run/$', views.ExecuteImportView.as_view(), name='import_execute'),
]
