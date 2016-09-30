import six
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils.datetime_safe import date
from django.conf import settings

from swiftwind.billing_cycle.cycles import Monthly
from swiftwind.billing_cycle.models import BillingCycle


class BillingCycleConstraintTestCase(TransactionTestCase):

    def test_constraint_non_overlapping(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 1, 25), date(2016, 2, 25))
            )

    def test_constraint_adjacent(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        with self.assertRaises(IntegrityError):
            BillingCycle.objects.create(
                date_range=(date(2016, 2, 2), date(2016, 3, 1))
            )

    def test_constraint_ok(self):
        BillingCycle.objects.create(
            date_range=(date(2016, 1, 1), date(2016, 2, 1))
        )
        BillingCycle.objects.create(
            date_range=(date(2016, 2, 1), date(2016, 3, 1))
        )
        # No errors


class BillingCycleTestCase(TestCase):

    def test_populate_deletion(self):
        cycle1 = BillingCycle.objects.create(date_range=(date(2016, 4, 1), date(2016, 5, 1)))  # keep
        cycle2 = BillingCycle.objects.create(date_range=(date(2016, 5, 1), date(2016, 6, 1)))  # keep
        cycle3 = BillingCycle.objects.create(date_range=(date(2016, 6, 1), date(2016, 7, 1)))  # keep
        cycle4 = BillingCycle.objects.create(date_range=(date(2016, 7, 1), date(2016, 8, 1)))  # delete

        with self.settings(SWIFTWIND_BILLING_CYCLE_YEARS=2):
            BillingCycle._populate(as_of=date(2016, 6, 1))

        # 3 previous cycles kept, and 24 new ones created
        self.assertEqual(BillingCycle.objects.count(), 3 + 24)

        first = BillingCycle.objects.first()
        last = BillingCycle.objects.last()
        self.assertEqual(first.date_range.lower, date(2016, 4, 1))
        self.assertEqual(last.date_range.lower, date(2018, 6, 1))

        self.assertIn(cycle1, BillingCycle.objects.all())
        self.assertIn(cycle2, BillingCycle.objects.all())
        self.assertIn(cycle3, BillingCycle.objects.all())
        self.assertNotIn(cycle4, BillingCycle.objects.all())


class CycleTestCase(TestCase):

    def test_monthly(self):
        cycle = Monthly()

        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 15), inclusive=True),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_next_cycle_start_date(date(2016, 6, 1), inclusive=True),
            date(2016, 6, 1)
        )

        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 15)),
            date(2016, 7, 1)
        )
        self.assertEqual(
            cycle.get_cycle_end_date(date(2016, 6, 1)),
            date(2016, 7, 1)
        )

        ranges = cycle.generate_date_ranges(date(2016, 10, 15))
        self.assertEqual(six.next(ranges), (date(2016, 11, 1), date(2016, 12, 1)))
        self.assertEqual(six.next(ranges), (date(2016, 12, 1), date(2017, 1, 1)))
        self.assertEqual(six.next(ranges), (date(2017, 1, 1), date(2017, 2, 1)))
