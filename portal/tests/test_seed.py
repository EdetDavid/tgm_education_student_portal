from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from portal.models import Course, Event, Inquiry, Student


class DemoSeedTests(TestCase):
    def test_seed_is_varied_idempotent_and_preserves_edits(self):
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Course.objects.count(), 20)
        self.assertEqual(Event.objects.count(), 3)
        self.assertEqual(Inquiry.objects.count(), 240)
        self.assertEqual(Student.objects.count(), 240)
        self.assertEqual(Inquiry.objects.values('course_id').distinct().count(), 20)
        self.assertEqual(Inquiry.objects.values('status').distinct().count(), 4)
        self.assertEqual(Inquiry.objects.values('destination').distinct().count(), 8)
        self.assertGreater(Inquiry.objects.values('created_at__date').distinct().count(), 30)
        sample = Inquiry.objects.first()
        sample.internal_notes = 'Keep my staff notes'
        sample.save()
        course = Course.objects.first()
        course.price = 34500
        course.save()
        call_command('seed_demo', stdout=StringIO())
        sample.refresh_from_db()
        course.refresh_from_db()
        self.assertEqual(sample.internal_notes, 'Keep my staff notes')
        self.assertEqual(course.price, 34500)
        self.assertEqual(Inquiry.objects.count(), 240)

    def test_seed_can_prepare_a_catalog_without_sample_inquiries(self):
        call_command('seed_demo', inquiries=0, stdout=StringIO())
        self.assertEqual(Course.objects.count(), 20)
        self.assertEqual(Event.objects.count(), 3)
        self.assertEqual(Inquiry.objects.count(), 0)
