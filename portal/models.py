from django.db import models
from django.db.models.functions import Lower
from django.contrib.auth.models import User


class Student(models.Model):
    email = models.EmailField()
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    location = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            Lower('email'), name='student_email_case_unique')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)


class StaffProfile(models.Model):
    ROLE_CHOICES = [('Admin', 'Admin'), ('Counsellor', 'Counsellor')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    staff_id = models.CharField(max_length=80, unique=True)
    organisation_code_hash = models.CharField(max_length=128)


class PortalAccessCode(models.Model):
    name = models.CharField(max_length=40, unique=True, default='super_admin')
    code_hash = models.CharField(max_length=128)
    updated_at = models.DateTimeField(auto_now=True)


class Course(models.Model):
    name = models.CharField(max_length=160)
    institution = models.CharField(max_length=160, default='TGM Education Partner University')
    region = models.CharField(max_length=80, default='United Kingdom')
    study_country = models.CharField(max_length=100, default='United Kingdom')
    study_city = models.CharField(max_length=100, default='London')
    level = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    location = models.CharField(max_length=100)
    intakes = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    def as_dict(self): return {'id': self.id, 'name': self.name, 'level': self.level, 'price': str(
        self.price), 'location': self.location, 'intakes': self.intakes}


class CourseOffering(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offerings')
    region = models.CharField(max_length=80)
    institution = models.CharField(max_length=160)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['course', 'institution', 'city'], name='course_offering_unique')]
        ordering = ['region', 'country', 'institution']


class Event(models.Model):
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=80)
    venue = models.CharField(max_length=160)
    date = models.DateField()
    time = models.TimeField()
    capacity = models.PositiveIntegerField(default=100)
    def as_dict(self): return {'id': self.id, 'name': self.name, 'city': self.city, 'venue': self.venue,
                               'date': self.date.isoformat(), 'time': self.time.strftime('%H:%M'), 'capacity': self.capacity}


class Inquiry(models.Model):
    STATUS_CHOICES = [('New', 'New'), ('Contacted', 'Contacted'),
                      ('Converted', 'Converted'), ('Closed', 'Closed')]
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name='inquiries')
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    programme_type = models.CharField(max_length=40, default='Undergraduate')
    intake = models.CharField(max_length=40)
    destination = models.CharField(max_length=100)
    destination_city = models.CharField(max_length=100, blank=True)
    student_location = models.CharField(max_length=120)
    event = models.ForeignKey(Event, on_delete=models.PROTECT)
    message = models.TextField(blank=True)
    reference = models.CharField(max_length=20, unique=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='New')
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'course', 'event',
                         '-created_at'], name='inquiry_duplicate_idx'),
            models.Index(fields=['-created_at', '-id'],
                         name='inquiry_recent_idx'),
            models.Index(fields=['status', '-created_at'],
                         name='inquiry_status_date_idx'),
            models.Index(fields=['course', '-created_at'],
                         name='inquiry_course_date_idx'),
            models.Index(fields=['event', '-created_at'],
                         name='inquiry_event_date_idx'),
            models.Index(fields=['intake'], name='inquiry_intake_idx'),
            models.Index(fields=['destination'],
                         name='inquiry_destination_idx'),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        if not self.student_id:
            self.student, _ = Student.objects.get_or_create(email=self.email, defaults={
                'full_name': self.full_name, 'phone': self.phone, 'location': self.student_location,
            })
        return super().save(*args, **kwargs)
