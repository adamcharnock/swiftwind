from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from swiftwind.core.models import Settings
from swiftwind.utilities.testing import DataProvider


class SetupViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.view_url = reverse('setup:index')

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('form', context)

    def test_post_valid(self):
        response = self.client.post(self.view_url, data={
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'mypassword',
            'password2': 'mypassword',
            'default_currency': 'GBP',
            'additional_currencies': ['EUR', 'USD'],
        })
        context = response.context
        if response.context:
            self.assertFalse(context['formset'].errors)

        user = User.objects.get()
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('mypassword'))
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

        settings = Settings.objects.get()
        self.assertEqual(settings.default_currency, 'GBP')
        self.assertEqual(settings.additional_currencies, ['EUR', 'USD'])

        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_can_load_dashboard_after_setup(self):
        self.client.post(self.view_url, data={
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'mypassword',
            'password2': 'mypassword',
            'default_currency': 'GBP',
            'additional_currencies': ['EUR', 'USD'],
        })

        # Now check we can load the dashboard
        response = self.client.get(reverse('dashboard:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_get_when_already_setup(self):
        Settings.objects.create()
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 302)

    def test_post_when_already_setup(self):
        Settings.objects.create()
        response = self.client.post(self.view_url)
        self.assertEqual(response.status_code, 302)
