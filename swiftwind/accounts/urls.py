from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.OverviewView.as_view(), name='overview'),
    url(r'^housemate/(?P<uuid>.*)/$', views.HousemateStatementView.as_view(), name='housemate_statement'),
    url(r'^housemate/(?P<uuid>.*)/(?P<date>\d{4}-\d{2}-\d{2})/$', views.HousemateStatementView.as_view(), name='housemate_statement_historical'),
    url(r'^email/(?P<uuid>.*)/(?P<date>\d{4}-\d{2}-\d{2})/$', views.StatementEmailView.as_view(), name='housemate_statement_email'),
]
