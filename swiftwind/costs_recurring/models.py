from uuid import uuid4
from django.db import models
from django.utils import timezone
from django_smalluuid.models import SmallUUIDField
from django_smalluuid.models import uuid_default
from model_utils import Choices


class RecurringCost(models.Model):
    TYPES = Choices(
        (
            'normal',
            "We will not have spent this yet. We will estimate "
            "a fixed amount per billing cycle."
        ),
        (
            'arrears_balance',
            "We will have already spent this in the previous billing "
            "cycle, so bill the account's balance."),
        (
            'arrears_balance',
            "We will have already spent this in the previous cycle, "
            "so bill the total amount spent in the previous cycle."
        ),
    )

    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    from_accounts = models.ManyToManyField('hordak.Account',
                                           through='costs_recurring.RecurringCostSplit',
                                           related_name='outbound_costs')
    to_account = models.ForeignKey('hordak.Account', related_name='inbound_costs')
    is_active = models.BooleanField(default=True, help_text='Uncheck to disable this cost')
    fixed_amount = models.DecimalField(max_digits=13, decimal_places=2)
    type = models.CharField(max_length=20, choices=TYPES, default=TYPES.normal)


class RecurringCostSplit(models.Model):
    recurring_cost = models.ForeignKey(RecurringCost)
    from_account = models.ForeignKey('hordak.Account')
    portion = models.DecimalField(max_digits=13, decimal_places=2)

