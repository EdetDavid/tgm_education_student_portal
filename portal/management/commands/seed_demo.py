from datetime import time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from portal.intakes import available_intakes
from portal.models import Course, Event, Inquiry, Student
from portal.serializers import DESTINATIONS


COURSES = [
    'Business Management', 'Computer Science', 'Data Science', 'Cyber Security',
    'International Relations', 'Engineering Management', 'Accounting and Finance',
    'Marketing', 'Artificial Intelligence', 'Public Health', 'Architecture', 'Law',
    'Psychology', 'Media and Communications', 'Project Management', 'Biomedical Science',
    'Hospitality Management', 'Education', 'Software Engineering', 'Economics',
]
EVENTS = [
    ('TGM Education Lagos', 'Lagos', 'Eko Hotel'),
    ('TGM Education Abuja', 'Abuja', 'Transcorp Hilton'),
    ('TGM Education Accra', 'Accra', 'Kempinski Hotel'),
]
FIRST_NAMES = ['Amara', 'Chidi', 'Zara', 'Kwame', 'Ada', 'Tunde', 'Amina', 'Kofi', 'Zainab', 'Emeka', 'Seyi', 'Akua']
LAST_NAMES = ['Okafor', 'Mensah', 'Musa', 'Adebayo', 'Owusu', 'Ibrahim', 'Eze', 'Osei', 'Bello', 'Balogun']
LOCATIONS = ['Lagos, Nigeria', 'Abuja, Nigeria', 'Accra, Ghana', 'Kumasi, Ghana', 'Ibadan, Nigeria', 'Port Harcourt, Nigeria']


class Command(BaseCommand):
    help = 'Add 20 courses, 3 events and 240 varied sample inquiries without replacing existing data.'

    def add_arguments(self, parser):
        parser.add_argument('--inquiries', type=int, default=240, help='Number of sample inquiries (default: 240).')

    @transaction.atomic
    def handle(self, *args, **options):
        count = options['inquiries']
        if not 0 <= count <= 10000:
            raise CommandError('--inquiries must be between 0 and 10000.')
        courses = []
        for index, name in enumerate(COURSES):
            course, _ = Course.objects.get_or_create(name=name, defaults={
                'level': 'Postgraduate' if index % 3 == 0 else 'Undergraduate',
                'price': 18000 + index * 450, 'location': ['London', 'Manchester', 'Birmingham'][index % 3],
                'intakes': ['January', 'May', 'September'],
            })
            courses.append(course)
        events = []
        for index, (name, city, venue) in enumerate(EVENTS):
            event, _ = Event.objects.get_or_create(name=name, defaults={
                'city': city, 'venue': venue, 'date': timezone.localdate() + timedelta(days=14 + index * 7),
                'time': time(10, 0), 'capacity': 120,
            })
            events.append(event)
        created = 0
        for index in range(count):
            reference = f'DEMO-{index + 1:06d}'
            if Inquiry.objects.filter(reference=reference).exists():
                continue
            course = courses[index % len(courses)]
            email = f'student{index + 1:04d}@example.com'
            full_name = f'{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]}'
            phone = f'+234 80{index + 10000000:08d}'
            location = LOCATIONS[index % len(LOCATIONS)]
            student, _ = Student.objects.get_or_create(email=email, defaults={
                'full_name': full_name, 'phone': phone, 'location': location,
            })
            intakes = available_intakes(course.intakes)
            if not intakes:
                raise CommandError(f'{course.name} has no valid intakes; add one before seeding.')
            inquiry = Inquiry.objects.create(
                student=student, full_name=full_name, email=email, phone=phone, course=course,
                intake=intakes[(index // len(courses)) % len(intakes)],
                destination=DESTINATIONS[(index // 3) % len(DESTINATIONS)],
                student_location=location, event=events[index % len(events)],
                message=['Please tell me about scholarships.', 'Can I study part-time?', '', 'What documents do I need?'][index % 4],
                reference=reference, status=Inquiry.STATUS_CHOICES[(index // 5) % 4][0],
                internal_notes='Sample record for the assessment demo.',
            )
            # Spread activity across 60 days so the timeline is useful, not a single bar.
            Inquiry.objects.filter(pk=inquiry.pk).update(
                created_at=timezone.now() - timedelta(days=index % 60, hours=index % 12))
            created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Demo ready: {Course.objects.count()} courses, {Event.objects.count()} events, '
            f'{Inquiry.objects.count()} inquiries ({created} sample inquiries added). Existing records preserved.'))
