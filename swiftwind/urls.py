from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import TemplateView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from graphene.contrib.django.views import GraphQLView
from django_filters.views import FilterView

from swiftwind.accounts.filters import AccountFilter, TransactionFilter
from swiftwind.schema import schema

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'swiftwind.views.home', name='home'),
    # url(r'^swiftwind/', include('swiftwind.foo.urls')),

    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^$', TemplateView.as_view(template_name='home.html')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'', include('swiftwind.core.urls', namespace='core', app_name='core')),
    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'core/login.html'}),
    url(r'^go/', include('loginurl.urls')),

    url(r'^filter/accounts/$', FilterView.as_view(filterset_class=AccountFilter, template_name='accounts/filter.html')),
    url(r'^filter/transactions/$', FilterView.as_view(filterset_class=TransactionFilter, template_name='accounts/filter.html')),

    url(r'^graphql',
        login_required(
            csrf_exempt(GraphQLView.as_view(schema=schema))
        )
    ),
    url(r'^graphiql', include('django_graphiql.urls')),
)
