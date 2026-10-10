from datetime import time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from portal.intakes import available_intakes
from portal.models import Course, Event, Inquiry, PortalOption, Student


COURSES = [
    'Business Management', 'Computer Science', 'Data Science', 'Cyber Security',
    'International Relations', 'Engineering Management', 'Accounting and Finance',
    'Marketing', 'Artificial Intelligence', 'Public Health', 'Architecture', 'Law',
    'Psychology', 'Media and Communications', 'Project Management', 'Biomedical Science',
    'Hospitality Management', 'Education', 'Software Engineering', 'Economics',
]
CATALOGUE = [
    ('University of Manchester', 'Europe', 'United Kingdom', 'Manchester'),
    ('University of Birmingham', 'Europe', 'United Kingdom', 'Birmingham'),
    ('University of Edinburgh', 'Europe', 'United Kingdom', 'Edinburgh'),
    ('University of Toronto', 'North America', 'Canada', 'Toronto'),
    ('McGill University', 'North America', 'Canada', 'Montreal'),
    ('University of British Columbia', 'North America', 'Canada', 'Vancouver'),
    ('University of Melbourne', 'Oceania', 'Australia', 'Melbourne'),
    ('UNSW Sydney', 'Oceania', 'Australia', 'Sydney'),
    ('University of Sydney', 'Oceania', 'Australia', 'Sydney'),
    ('Trinity College Dublin', 'Europe', 'Ireland', 'Dublin'),
    ('University College Dublin', 'Europe', 'Ireland', 'Dublin'),
    ('University of Amsterdam', 'Europe', 'Netherlands', 'Amsterdam'),
    ('Technical University of Munich', 'Europe', 'Germany', 'Munich'),
    ('Sorbonne University', 'Europe', 'France', 'Paris'),
    ('University of California, Berkeley', 'North America', 'United States', 'Berkeley'),
    ('University of Washington', 'North America', 'United States', 'Seattle'),
    ('Northeastern University', 'North America', 'United States', 'Boston'),
    ('University of Glasgow', 'Europe', 'United Kingdom', 'Glasgow'),
    ('University of Leeds', 'Europe', 'United Kingdom', 'Leeds'),
    ('University of Nottingham', 'Europe', 'United Kingdom', 'Nottingham'),
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
        destinations = list(PortalOption.objects.filter(
            option_type='destination', active=True
        ).order_by('sort_order', 'value').values_list('value', flat=True))
        if count and not destinations:
            raise CommandError('Add at least one active study destination before seeding inquiries.')
        courses = []
        for index, name in enumerate(COURSES):
            institution, region, country, city = CATALOGUE[index]
            course, _ = Course.objects.get_or_create(name=name, defaults={
                'institution': institution, 'region': region, 'study_country': country, 'study_city': city,
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
        existing_references = set(Inquiry.objects.filter(
            reference__startswith='DEMO-').values_list('reference', flat=True))
        emails = [f'student{index + 1:04d}@example.com' for index in range(count)]
        students = {student.email.lower(): student for student in
                    Student.objects.annotate(email_key=Lower('email')).filter(email_key__in=emails)}
        new_students = []
        rows = []
        for index in range(count):
            reference = f'DEMO-{index + 1:06d}'
            if reference in existing_references:
                continue
            course = courses[index % len(courses)]
            email = f'student{index + 1:04d}@example.com'
            full_name = f'{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]}'
            phone = f'+234 80{index + 10000000:08d}'
            location = LOCATIONS[index % len(LOCATIONS)]
            if email not in students:
                new_students.append(Student(email=email, full_name=full_name, phone=phone, location=location))
            intakes = available_intakes(course.intakes)
            if not intakes:
                raise CommandError(f'{course.name} has no valid intakes; add one before seeding.')
            inquiry = Inquiry(
                full_name=full_name, email=email, phone=phone, course=course,
                intake=intakes[(index // len(courses)) % len(intakes)],
                destination=destinations[(index // 3) % len(destinations)],
                student_location=location, event=events[index % len(events)],
                message=['Please tell me about scholarships.', 'Can I study part-time?', '', 'What documents do I need?'][index % 4],
                reference=reference, status=Inquiry.STATUS_CHOICES[(index // 5) % 4][0],
                internal_notes='Sample record for the assessment demo.',
            )
            # Spread activity across 60 days so the timeline is useful, not a single bar.
            rows.append((inquiry, timezone.now() - timedelta(days=index % 60, hours=index % 12)))
        # Keep a cloud seed to a few batches rather than thousands of network
        # round trips inside a long-lived transaction.
        Student.objects.bulk_create(new_students, batch_size=500)
        students = {student.email.lower(): student for student in
                    Student.objects.annotate(email_key=Lower('email')).filter(email_key__in=emails)}
        inquiries = [row[0] for row in rows]
        for inquiry in inquiries:
            inquiry.student = students[inquiry.email]
        Inquiry.objects.bulk_create(inquiries, batch_size=500)
        for inquiry, submitted_at in rows:
            inquiry.created_at = submitted_at
        Inquiry.objects.bulk_update(inquiries, ['created_at'], batch_size=500)
        created = len(inquiries)
        self.stdout.write(self.style.SUCCESS(
            f'Demo ready: {Course.objects.count()} courses, {Event.objects.count()} events, '
            f'{Inquiry.objects.count()} inquiries ({created} sample inquiries added). Existing records preserved.'))
