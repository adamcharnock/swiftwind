from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'^$', views.HousemateListView.as_view(), name='list'),
    url(r'^create/$', views.HousemateCreateView.as_view(), name='create'),
]
