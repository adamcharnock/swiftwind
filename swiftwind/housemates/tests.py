from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from hordak.models import Account
from hordak.tests.utils import DataProvider
from swiftwind.housemates.forms import HousemateUpdateForm

from swiftwind.housemates.models import Housemate


class HousemateCreateViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.login()

        self.view_url = reverse('housemates:create')
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            first_name='Joe',
            last_name='Bloggs',
        )
        self.parent_account = self.account(
            name='Housemate Income',
            type=Account.TYPES.income,
        )

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertIn('form', response.context)

    def test_post_success_existing_user_existing_account(self):
        account = self.account(
            name='Existing Account',
            parent=self.parent_account,
        )

        response = self.client.post(self.view_url, data=dict(
            existing_user=self.user.username,
            account=account.uuid,
        ))
        if response.context and 'form' in response.context:
            self.assertFalse(response.context['form'].errors)

        self.assertEqual(Housemate.objects.count(), 1)
        housemate = Housemate.objects.get()
        self.assertEqual(housemate.user, self.user)
        self.assertEqual(housemate.account, account)

    def test_post_success_existing_user_new_account(self):
        response = self.client.post(self.view_url, data=dict(
            existing_user=self.user.username,
        ))
        if response.context and 'form' in response.context:
            self.assertFalse(response.context['form'].errors)

        self.assertEqual(Housemate.objects.count(), 1)
        housemate = Housemate.objects.get()
        self.assertEqual(housemate.user, self.user)
        self.assertEqual(housemate.account.parent, self.parent_account)
        self.assertEqual(housemate.account.name, 'Joe Bloggs')

    def test_post_success_new_user_existing_account(self):
        account = self.account(
            name='Existing Account',
            parent=self.parent_account,
        )

        response = self.client.post(self.view_url, data=dict(
            new_username='newuser',
            new_email='new@example.com',
            new_first_name='New',
            new_last_name='User',
            account=account.uuid,
        ))
        if response.context and 'form' in response.context:
            self.assertFalse(response.context['form'].errors)

        account.refresh_from_db()
        self.assertEqual(Housemate.objects.count(), 1)
        housemate = Housemate.objects.get()
        self.assertEqual(housemate.user.username, 'newuser')
        self.assertEqual(housemate.user.email, 'new@example.com')
        self.assertEqual(housemate.user.first_name, 'New')
        self.assertEqual(housemate.user.last_name, 'User')
        self.assertEqual(housemate.account, account)
        self.assertEqual(housemate.account.name, 'Existing Account')
        self.assertEqual(housemate.account.currencies, ['EUR'])

    def test_post_success_new_user_new_account(self):
        account = self.account(
            name='Existing Account',
            parent=self.parent_account,
        )

        response = self.client.post(self.view_url, data=dict(
            new_username='newuser',
            new_email='new@example.com',
            new_first_name='New',
            new_last_name='User',
        ))
        if response.context and 'form' in response.context:
            self.assertFalse(response.context['form'].errors)

        account.refresh_from_db()
        self.assertEqual(Housemate.objects.count(), 1)
        housemate = Housemate.objects.get()
        self.assertEqual(housemate.user.username, 'newuser')
        self.assertEqual(housemate.user.email, 'new@example.com')
        self.assertEqual(housemate.user.first_name, 'New')
        self.assertEqual(housemate.user.last_name, 'User')

        self.assertEqual(housemate.account.parent, self.parent_account)
        self.assertEqual(housemate.account.name, 'New User')
        self.assertEqual(housemate.account.currencies, ['EUR'])


class HousemateUpdateViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.login()
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            first_name='Joe',
            last_name='Bloggs',
        )
        self.parent_account = self.account(
            name='Housemate Income',
            type=Account.TYPES.income,
        )
        self.housemate = Housemate.objects.create(
            user=self.user,
            account=self.account('Joe Blogs', parent=self.parent_account)
        )
        self.view_url = reverse('housemates:update', args=[self.housemate.uuid])

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertIn('form', response.context)

    def test_simple(self):
        response = self.client.post(self.view_url, data=dict(
            username='newusername',
            email='new@email.com',
            first_name='Jim',
            last_name='Smith',
        ))
        if response.context and 'form' in response.context:
            self.assertFalse(response.context['form'].errors)

        self.assertEqual(Housemate.objects.count(), 1)
        housemate = Housemate.objects.get()
        user = housemate.user
        account = housemate.account

        self.assertEqual(user.username, 'newusername')
        self.assertEqual(user.email, 'new@email.com')
        self.assertEqual(user.first_name, 'Jim')
        self.assertEqual(user.last_name, 'Smith')
        self.assertEqual(account.name, 'Jim Smith')


class HousemateUpdateFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.other_user = User.objects.create(
            username='otheruser',
            email='other@user.com',
            first_name='Other',
            last_name='User',
        )
        self.user = User.objects.create(
            username='testuser',
            email='test@example.com',
            first_name='Joe',
            last_name='Bloggs',
        )
        self.parent_account = self.account(
            name='Housemate Income',
            type=Account.TYPES.income,
        )
        self.housemate = Housemate.objects.create(
            user=self.user,
            account=self.account('Joe Blogs', parent=self.parent_account)
        )

    def test_valid(self):
        form = HousemateUpdateForm(data=dict(
            username='testuser',
            email='test@example.com',
            first_name='Joe',
            last_name='Bloggs',
        ), instance=self.housemate)
        self.assertTrue(form.is_valid(), form.errors)

    def test_username_in_use(self):
        form = HousemateUpdateForm(data=dict(
            username='otheruser',
            email='test@example.com',
            first_name='Joe',
            last_name='Bloggs',
        ), instance=self.housemate)
        self.assertFalse(form.is_valid())

    def test_email_in_use(self):
        form = HousemateUpdateForm(data=dict(
            username='testuser',
            email='other@user.com',
            first_name='Joe',
            last_name='Bloggs',
        ), instance=self.housemate)
        self.assertFalse(form.is_valid())
