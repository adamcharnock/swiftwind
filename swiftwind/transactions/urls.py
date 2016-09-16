from django.conf.urls import url
from django.contrib import admin

from . import views

urlpatterns = [
    url(r'$', views.CreateTransactionView.as_view(), name='create'),
]
