from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from hordak.models import Account
from mptt.forms import TreeNodeChoiceField

from .models import Housemate


class HousemateForm(forms.ModelForm):
    existing_user = forms.ModelChoiceField(required=False, to_field_name='username',
                                           queryset=get_user_model().objects.filter(housemate=None, is_active=True),
    )
    new_username = forms.CharField(required=False, max_length=150)
    new_email = forms.EmailField(required=False)
    new_first_name = forms.CharField(required=False)
    new_last_name = forms.CharField(required=False)
    account = TreeNodeChoiceField(Account.objects.all(), required=False, to_field_name='uuid',
                                  empty_label='-- Create new account for user --')

    class Meta:
        model = Housemate
        fields = []
        # Prevent django from prematurely failing the account for being null
        exclude = ['account']

    def clean_account(self):
        """Ensure this is an income account"""
        account = self.cleaned_data['account']
        if not account:
            return

        if account.type != Account.TYPES.income:
            raise ValidationError('Account must be an income account')

        try:
            account.housemate
        except Housemate.DoesNotExist:
            pass
        else:
            raise ValidationError('Account already has a housemate')

        return account

    def clean(self):
        if self.errors:
            return

        User = get_user_model()
        existing_user_specified = bool(self.cleaned_data.get('existing_user'))
        new_user_specified = \
            bool(self.cleaned_data.get('new_username')) or \
            bool(self.cleaned_data.get('new_email')) or \
            bool(self.cleaned_data.get('new_first_name')) or \
            bool(self.cleaned_data.get('new_last_name'))

        # Ensure the use has done one or the other. Not both. Not neither.
        if existing_user_specified and new_user_specified:
            raise ValidationError('Either select an existing user or enter details for a new user')

        if not existing_user_specified and not new_user_specified:
            raise ValidationError('Either select an existing user or enter details for a new user')

        # Make sure the required data has been provided to create a new user
        if new_user_specified:
            username = self.cleaned_data.get('new_username')
            email = self.cleaned_data.get('new_email')
            first_name = self.cleaned_data.get('new_first_name')
            last_name = self.cleaned_data.get('new_last_name')

            if not username:
                raise ValidationError('Username must be specified to create a new user')

            if not email:
                raise ValidationError('Email must be specified to create a new user')

            if not first_name:
                raise ValidationError('First name must be specified to create a new user')

            if not last_name:
                raise ValidationError('Last name must be specified to create a new user')

            if User.objects.filter(username=username).count():
                raise ValidationError('Username already in use')

            if User.objects.filter(email=email).count():
                raise ValidationError('Email already in use')

            # Let's be thorough
            self.cleaned_data['existing_user'] = None
        else:
            self.cleaned_data['new_username'] = None
            self.cleaned_data['new_email'] = None
            self.cleaned_data['new_first_name'] = None
            self.cleaned_data['new_last_name'] = None

    def save(self, commit=True):
        User = get_user_model()
        user = self.cleaned_data.get('existing_user')
        account = self.cleaned_data.get('account')

        # Create a user if we need to
        if not user:
            user = User.objects.create(
                username=self.cleaned_data.get('new_username'),
                email=self.cleaned_data.get('new_email'),
                first_name=self.cleaned_data.get('new_first_name'),
                last_name=self.cleaned_data.get('new_last_name'),
            )

        # Create an account if we need to
        if not account:
            # TODO: Generalize, housemate parent account should be configurable
            parent = Account.objects.get(name='Housemate Income')

            # Figure out the next highest code
            # TODO: Move this logic into hordak's AccountManager
            codes = Account.objects.filter(parent=parent).values_list('code', flat=True)
            codes = list(filter(lambda code: code.isdigit(), codes))

            if not codes:
                code = '00'
            else:
                max_code = max(codes)
                code_length = len(max_code)
                code = str(int(max_code) + 1).zfill(code_length)

            account = Account.objects.create(
                name=user.get_full_name(),
                parent=parent,
                code=code,
                currencies=[settings.SWIFTWIND_DEFAULT_CURRENCY],
            )

        self.instance.user = user
        self.instance.account = account

        return super(HousemateForm, self).save(commit)
