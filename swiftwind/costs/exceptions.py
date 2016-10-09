

class CannotEnactUnenactableRecurringCostError(Exception): pass


class CannotRecreateTransactionOnRecurredCost(Exception): pass


class NoSplitsFoundForRecurringCost(Exception): pass


class ProvidedBillingCycleBeginsBeforeInitialBillingCycle(Exception): pass


class RecurringCostAlreadyEnactedForBillingCycle(Exception): pass
