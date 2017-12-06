from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.BillingCycleListView.as_view(), name='list'),
    url(r'^enact/(?P<uuid>.+)/$', views.CreateTransactionsView.as_view(), name='enact'),
    url(r'^reenact/(?P<uuid>.+)/$', views.RecreateTransactionsView.as_view(), name='reenact'),
    url(r'^send/(?P<uuid>.+)/$', views.SendNotificationsView.as_view(), name='send'),
]
