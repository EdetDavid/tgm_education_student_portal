import re
import calendar
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Course, Event, Inquiry
from .intakes import available_intakes

# create serializers 

DESTINATIONS = ['United Kingdom', 'United States', 'Canada', 'Australia',
                'Ireland', 'Germany', 'France', 'Netherlands']


class CourseSerializer(serializers.ModelSerializer):
    intakes = serializers.ListField(child=serializers.ChoiceField(
        choices=list(calendar.month_name)[1:]), allow_empty=False)
    price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.00'))

    class Meta:
        model = Course
        fields = ['id', 'name', 'level', 'price',
                  'location', 'intakes', 'active']
        read_only_fields = ['id']


class PublicCourseSerializer(serializers.ModelSerializer):
    intake_options = serializers.SerializerMethodField()

    def get_intake_options(self, course):
        return available_intakes(course.intakes)

    class Meta:
        model = Course
        fields = ['id', 'name', 'level', 'price',
                  'location', 'intakes', 'intake_options']


class EventSerializer(serializers.ModelSerializer):
    capacity = serializers.IntegerField(min_value=1)

    class Meta:
        model = Event
        fields = ['id', 'name', 'city', 'venue', 'date', 'time', 'capacity']
        read_only_fields = ['id']


class StudentInquiryCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(
        min_length=2, max_length=120, trim_whitespace=True)
    email = serializers.EmailField(max_length=254, trim_whitespace=True)
    phone = serializers.CharField(
        min_length=7, max_length=30, trim_whitespace=True)
    course_id = serializers.PrimaryKeyRelatedField(
        source='course', queryset=Course.objects.filter(active=True))
    intake = serializers.CharField(max_length=40, trim_whitespace=True)
    destination = serializers.ChoiceField(choices=DESTINATIONS)
    student_location = serializers.CharField(
        max_length=120, trim_whitespace=True)
    event_id = serializers.PrimaryKeyRelatedField(
        source='event', queryset=Event.objects.all())
    message = serializers.CharField(
        max_length=1000, allow_blank=True, required=False, trim_whitespace=True,
        style={'base_template': 'textarea.html'})

    def validate_email(self, value):
        return value.lower()

    def validate_student_location(self, value):
        parts = [part.strip() for part in value.rsplit(',', 1)]
        if len(parts) != 2 or not parts[0] or len(parts[1]) < 2:
            raise serializers.ValidationError(
                'Enter your city and country, for example Lagos, Nigeria.')
        return ', '.join(parts)

    def validate_phone(self, value):
        if not re.fullmatch(r'[+\d().\-\s]{7,30}', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15:
            raise serializers.ValidationError('Enter a valid phone number.')
        return value

    def validate(self, attrs):
        course = attrs['course']
        valid_intakes = available_intakes(course.intakes)
        if attrs['intake'] not in valid_intakes:
            raise serializers.ValidationError(
                {'intake': 'Choose an intake offered for this course.'})
        if attrs['event'].date < timezone.localdate():
            raise serializers.ValidationError(
                {'event_id': 'Choose an upcoming event.'})
        return attrs


class AdminInquirySerializer(serializers.ModelSerializer):
    course = serializers.CharField(source='course.name', read_only=True)
    course_id = serializers.IntegerField(read_only=True)
    price = serializers.DecimalField(
        source='course.price', max_digits=12, decimal_places=2, read_only=True)
    event = serializers.CharField(source='event.name', read_only=True)
    event_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Inquiry
        fields = ['id', 'reference', 'full_name', 'email', 'phone', 'course', 'course_id', 'price',
                  'intake', 'destination', 'student_location', 'event', 'event_id', 'message',
                  'status', 'internal_notes', 'created_at']


class AdminInquiryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = ['status', 'internal_notes']


class AdminLoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class AdminInquiryListUpdateSerializer(AdminInquiryUpdateSerializer):
    id = serializers.IntegerField(min_value=1)

    class Meta(AdminInquiryUpdateSerializer.Meta):
        fields = ['id', 'status', 'internal_notes']


class InquiryFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=200)
    course = serializers.IntegerField(required=False, min_value=1)
    event = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        required=False, choices=Inquiry.STATUS_CHOICES)
    intake = serializers.CharField(required=False, max_length=40)
    destination = serializers.CharField(required=False, max_length=100)
    student_location = serializers.CharField(required=False, max_length=120)
    ordering = serializers.ChoiceField(required=False, choices=[
        'created_at', '-created_at', 'full_name', '-full_name',
        'course__name', '-course__name', 'event__name', '-event__name',
        'intake', '-intake', 'status', '-status', 'reference', '-reference',
    ])
