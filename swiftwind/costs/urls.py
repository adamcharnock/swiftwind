from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^recurring/$', views.RecurringCostsView.as_view(), name='recurring'),
    url(r'^oneoff/$', views.OneOffCostsView.as_view(), name='one_off'),
    url(r'^recurring/create/$', views.CreateRecurringCostView.as_view(), name='create_recurring'),
    url(r'^oneoff/create/$', views.CreateOneOffCostView.as_view(), name='create_one_off'),
    url(r'^recurring/delete/(?P<uuid>.+)/$', views.DeleteRecurringCostView.as_view(), name='delete_recurring'),
    url(r'^oneoff/delete/(?P<uuid>.+)/$', views.DeleteOneOffCostView.as_view(), name='delete_one_off'),
    url(r'^recurring/archive/(?P<uuid>.+)/$', views.ArchiveRecurringCostView.as_view(), name='archive_recurring'),
    url(r'^oneoff/archive/(?P<uuid>.+)/$', views.ArchiveOneOffCostView.as_view(), name='archive_one_off'),
]
