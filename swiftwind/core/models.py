from django.contrib.postgres.fields.array import ArrayField
from django.db import models
from djmoney.settings import CURRENCY_CHOICES

from swiftwind.core.exceptions import CannotCreateMultipleSettingsInstances


class SettingsManager(models.Manager):

    def get(self):
        # TODO: Pull from cache
        try:
            return super(SettingsManager, self).get()
        except Settings.DoesNotExist:
            return super(SettingsManager, self).create()


class Settings(models.Model):
    """Store application-wide settings

    Each field is one setting. Only once instance of Settings can be created.

    The model is intentionally named Settings rather than Setting (as would
    be the Django convention), as a single model holds many settings.
    """
    default_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='EUR')
    additional_currencies = ArrayField(base_field=models.CharField(choices=CURRENCY_CHOICES, default=[], max_length=3),
                                       choices=CURRENCY_CHOICES,  # needed?
                                       default=[], blank=True)
    payment_information = models.TextField(default='', blank=True,
                                           help_text='Enter information on how payment should be made, such as the '
                                                     'bank account details housemates should pay into.')
    email_from_address = models.EmailField(default='', blank=True,
                                           help_text='What email address should emails appear to be sent from?')

    objects = SettingsManager()

    class Meta:
        verbose_name_plural = 'settings'

    def save(self, *args, **kwargs):
        if not self.pk and Settings.objects.exists():
            raise CannotCreateMultipleSettingsInstances('Only one Settings instance maybe created')
        super(Settings, self).save(*args, **kwargs)
        # TODO: Push changes into cache (possibly following a refresh_from_db() call)

    @property
    def currencies(self):
        return sorted({self.default_currency} | set(self.additional_currencies))
