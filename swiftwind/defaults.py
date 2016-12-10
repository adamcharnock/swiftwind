from django.conf import settings


def set_default(setting, value):
    if not hasattr(settings._wrapped, setting):
        setattr(settings._wrapped, setting, value)


set_default('SWIFTWIND_DEFAULT_CURRENCY', 'EUR')
set_default('SWIFTWIND_BILLING_CYCLE', 'swiftwind.billing_cycle.cycles.Monthly')
set_default('SWIFTWIND_BILLING_CYCLE_YEARS', 1)
