from django.contrib.sites.models import Site
from swiftwind.settings.models import Settings


def get_site_root():
    """

    Returns: (str) E.g. "https://mydomain.com"

    """
    site = Site.objects.get()
    settings = Settings.objects.get()
    protocol = 'https' if settings.use_https else 'http'
    return '{}://{}'.format(protocol, site.domain)
