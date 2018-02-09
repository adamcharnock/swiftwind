from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.BillingCycleListView.as_view(), name='list'),
    url(r'^enact/(?P<uuid>.+)/$', views.CreateTransactionsView.as_view(), name='enact'),
    url(r'^reenact/(?P<uuid>.+)/$', views.RecreateTransactionsView.as_view(), name='reenact'),
    url(r'^unenact/(?P<uuid>.+)/$', views.DeleteTransactionsView.as_view(), name='unenact'),
    url(r'^send/(?P<uuid>.+)/$', views.SendNotificationsView.as_view(), name='send'),
]
