from django.contrib import admin

from .models import Course, CourseOffering, Event, Inquiry, PortalAccessCode, StaffProfile, Student, University


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'price', 'location', 'active', 'intakes_display')
    list_filter = ('active', 'level', 'location')
    search_fields = ('name', 'level', 'location')
    list_editable = ('active',)
    ordering = ('name',)

    @admin.display(description='Available intakes')
    def intakes_display(self, obj):
        return ', '.join(obj.intakes or [])


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('course', 'region', 'institution', 'country', 'city', 'active')
    list_filter = ('region', 'country', 'active')
    search_fields = ('course__name', 'institution', 'country', 'city')
    list_editable = ('active',)
    ordering = ('course__name', 'region', 'institution')


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'city', 'active')
    list_filter = ('country', 'active')
    search_fields = ('name', 'country', 'city')
    list_editable = ('active',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'venue', 'date', 'time', 'capacity')
    list_filter = ('date', 'city')
    search_fields = ('name', 'city', 'venue')
    ordering = ('date', 'time')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'location', 'created_at', 'updated_at')
    search_fields = ('full_name', 'email', 'phone', 'location')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('reference', 'full_name', 'course', 'programme_type', 'destination_summary', 'event', 'status', 'created_at')
    list_filter = ('status', 'programme_type', 'intake', 'destination', 'event', 'course')
    search_fields = ('reference', 'full_name', 'email', 'phone', 'student__email', 'student__full_name')
    readonly_fields = ('reference', 'created_at')
    raw_id_fields = ('student', 'course', 'event')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    @admin.display(description='Study destination')
    def destination_summary(self, obj):
        return f'{obj.destination_city}, {obj.destination}' if obj.destination_city else obj.destination


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'role')
    list_filter = ('role',)
    search_fields = ('staff_id', 'user__username', 'user__email')
    readonly_fields = ('organisation_code_hash',)


@admin.register(PortalAccessCode)
class PortalAccessCodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at')
    readonly_fields = ('name', 'code_hash', 'updated_at')
    description = 'Access codes are managed through the Super Admin portal. Hashes are never shown in plain text.'
