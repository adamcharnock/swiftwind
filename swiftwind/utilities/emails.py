from django.test import RequestFactory

from .site import get_site_root


class EmailViewMixin(object):

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            site_root=get_site_root()
        )

    @classmethod
    def get_html(cls, **kwargs):
        fake_request = RequestFactory().get('/foo')
        view = cls.as_view()
        response = view(fake_request, **kwargs)
        response.render()
        return response.content.decode('utf8')
