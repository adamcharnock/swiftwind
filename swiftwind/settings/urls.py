from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', views.GeneralSettingsView.as_view(), name='general'),
    url(r'^technical/$', views.TechnicalSettingsView.as_view(), name='technical'),
    url(r'^teller/$', views.TellerSettingsView.as_view(), name='teller'),
    url(r'^email/$', views.EmailSettingsView.as_view(), name='email'),
]
