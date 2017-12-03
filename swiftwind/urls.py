"""example_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin

from hordak import views as hordak_views


# All the following will appear in the 'hordak' namespace (i.e. 'hordak:accounts_transactions')
hordak_urls = [
    url(r'^extra/transactions/create/$', hordak_views.TransactionCreateView.as_view(), name='transactions_create'),
    url(r'^extra/transactions/currency/$', hordak_views.CurrencyTradeView.as_view(), name='currency_trade'),
    url(r'^extra/transactions/reconcile/$', hordak_views.TransactionsReconcileView.as_view(), name='transactions_reconcile'),
    url(r'^extra/accounts/$', hordak_views.AccountListView.as_view(), name='accounts_list'),
    url(r'^extra/accounts/create/$', hordak_views.AccountCreateView.as_view(), name='accounts_create'),
    url(r'^extra/accounts/update/(?P<uuid>.+)/$', hordak_views.AccountUpdateView.as_view(), name='accounts_update'),
    url(r'^extra/accounts/(?P<uuid>.+)/$', hordak_views.AccountTransactionsView.as_view(), name='accounts_transactions'),

    url(r'^import/$', hordak_views.CreateImportView.as_view(), name='import_create'),
    url(r'^import/(?P<uuid>.*)/setup/$', hordak_views.SetupImportView.as_view(), name='import_setup'),
    url(r'^import/(?P<uuid>.*)/dry-run/$', hordak_views.DryRunImportView.as_view(), name='import_dry_run'),
    url(r'^import/(?P<uuid>.*)/run/$', hordak_views.ExecuteImportView.as_view(), name='import_execute'),
]

urlpatterns = [
    url(r'^housemates/', include('swiftwind.housemates.urls', namespace='housemates')),
    url(r'^accounts/', include('swiftwind.accounts.urls', namespace='accounts')),
    url(r'^costs/', include('swiftwind.costs.urls', namespace='costs')),
    url(r'^setup/', include('swiftwind.system_setup.urls', namespace='setup')),
    url(r'^', include('swiftwind.dashboard.urls', namespace='dashboard')),

    url(r'^', include(hordak_urls, namespace='hordak', app_name='hordak')),
]

