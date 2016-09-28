from django.conf import settings
from django.db import models
from django_smalluuid.models import SmallUUIDField, uuid_default
from hordak.models import Account


class Housemate(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    account = models.OneToOneField(Account, related_name='housemate', unique=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                related_name='housemate', blank=True, null=True,
                                unique=True)

