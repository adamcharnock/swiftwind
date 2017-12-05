from django.http.response import HttpResponseRedirect
from django.urls import reverse

from swiftwind.settings.models import Settings


class CheckSetupDoneMiddleware(object):
    """Send the user to the setup UI if no settings exist"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path_info.startswith('/setup'):
            if not Settings.objects.exists():
                return HttpResponseRedirect(reverse('setup:index'))

        return self.get_response(request)
