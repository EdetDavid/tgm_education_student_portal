from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User

from .models import ActivityLog, Course, CourseOffering, Event, Inquiry, PortalAccessCode, PortalOption, StaffProfile, Student, University
from .user_groups import assign_role_group, role_group_for_user


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class PortalUserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Portal access', {'fields': ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'groups')}),
    )
    list_display = ('username', 'email', 'portal_groups', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    filter_horizontal = ('groups', 'user_permissions')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        assign_role_group(form.instance, role_group_for_user(form.instance))

    @admin.display(description='Groups')
    def portal_groups(self, obj):
        return ', '.join(obj.groups.values_list('name', flat=True)) or 'No group'


@admin.register(Group)
class PortalGroupAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    filter_horizontal = ('permissions',)


class CourseOfferingInline(admin.TabularInline):
    model = CourseOffering
    extra = 1
    autocomplete_fields = ('university',)
    fields = ('university', 'region', 'institution', 'country', 'city', 'price', 'active')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'price', 'location', 'active', 'intakes_display')
    list_filter = ('active', 'level', 'location')
    search_fields = ('name', 'level', 'location')
    list_editable = ('active',)
    ordering = ('name',)
    inlines = (CourseOfferingInline,)

    @admin.display(description='Available intakes')
    def intakes_display(self, obj):
        return ', '.join(obj.intakes or [])


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('course', 'university', 'region', 'city', 'price', 'active')
    list_filter = ('region', 'country', 'active')
    search_fields = ('course__name', 'institution', 'university__name', 'country', 'city')
    autocomplete_fields = ('course', 'university')
    list_editable = ('active',)
    ordering = ('course__name', 'region', 'institution')


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'city', 'active')
    list_filter = ('country', 'active')
    search_fields = ('name', 'country', 'city')
    list_editable = ('active',)
    ordering = ('name',)


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
    list_display = ('reference', 'full_name', 'course', 'university_summary', 'programme_type', 'destination_summary', 'event', 'status', 'created_at')
    list_filter = ('status', 'programme_type', 'intake', 'destination', 'event', 'course', 'course_offering__university')
    search_fields = ('reference', 'full_name', 'email', 'phone', 'student__email', 'student__full_name', 'course_offering__university__name')
    readonly_fields = ('reference', 'created_at')
    raw_id_fields = ('student', 'course', 'course_offering', 'event')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    @admin.display(description='Study destination')
    def destination_summary(self, obj):
        return f'{obj.destination_city}, {obj.destination}' if obj.destination_city else obj.destination

    @admin.display(description='Selected university')
    def university_summary(self, obj):
        if not obj.course_offering:
            return '—'
        return obj.course_offering.university or obj.course_offering.institution


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'role')
    list_filter = ('role',)
    search_fields = ('staff_id', 'user__username', 'user__email')
    readonly_fields = ('organisation_code_hash',)


@admin.register(PortalAccessCode)
class PortalAccessCodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at')
    readonly_fields = ('name', 'code_hash', 'code_encrypted', 'updated_at')
    description = 'Access codes are managed through the Super Admin portal. Codes are encrypted at rest.'


@admin.register(PortalOption)
class PortalOptionAdmin(admin.ModelAdmin):
    list_display = ('option_type', 'value', 'sort_order', 'active')
    list_filter = ('option_type', 'active')
    search_fields = ('value',)
    list_editable = ('sort_order', 'active')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor_label', 'actor_role', 'action', 'entity_type', 'entity_id', 'summary')
    list_filter = ('actor_role', 'action', 'entity_type', 'created_at')
    search_fields = ('actor_label', 'action', 'entity_type', 'entity_id', 'summary')
    readonly_fields = ('actor', 'actor_label', 'actor_role', 'action', 'entity_type', 'entity_id', 'summary', 'details', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
