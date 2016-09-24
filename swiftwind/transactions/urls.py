from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', views.CreateTransactionView.as_view(), name='create'),
    url(r'^import/$', views.CreateImportView.as_view(), name='import_create'),
    url(r'^import/(?P<uuid>.*)/setup/$', views.SetupImportView.as_view(), name='import_setup'),
    url(r'^import/(?P<uuid>.*)/dry-run/$', views.DryRunImportView.as_view(), name='import_dry_run'),
]
