import csv
import uuid
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import Group
from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.utils.decorators import method_decorator
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from .models import Course, Event, Inquiry, Student, StaffProfile, PortalAccessCode
from .queries import filtered_inquiries
from .csv_export import spreadsheet_safe
from .serializers import (AdminInquirySerializer, AdminInquiryUpdateSerializer, AdminInquiryListUpdateSerializer,
                          AdminLoginSerializer, CourseSerializer, EventSerializer,
                          PublicCourseSerializer, StudentInquiryCreateSerializer, StaffSignupSerializer)


# create views

def csrf_failure(request, reason=''):
    return JsonResponse({'error': 'Your session could not be verified. Refresh the page and try again.'}, status=403)


class ApiRoot(APIView):
    """Student Portal API. Public resources are open; admin resources require a staff login."""

    def get(self, request):
        routes = {
            'courses': 'course-list', 'events': 'event-list',
            'submit_inquiry': 'inquiry-create', 'admin_dashboard': 'admin-dashboard',
            'admin_inquiries': 'admin-inquiries', 'admin_courses': 'admin-courses',
            'admin_events': 'admin-events', 'admin_filters': 'admin-filters',
            'browser_login': 'rest_framework:login',
        }
        return Response({key: reverse(name, request=request) for key, name in routes.items()})


class StudentCourseList(generics.ListAPIView):
    serializer_class = PublicCourseSerializer
    queryset = Course.objects.filter(active=True).order_by('name')
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get('q', '').strip()
        if len(query) > 200:
            raise ValidationError(
                {'q': 'Search must be at most 200 characters.'})
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(
                level__icontains=query) | Q(location__icontains=query))
        for field in ['level', 'region', 'study_country', 'study_city']:
            if self.request.query_params.get(field):
                queryset = queryset.filter(
                    **{f'{field}__iexact': self.request.query_params[field].strip()})
        return queryset

    def list(self, request, *args, **kwargs):
        return Response({'courses': self.get_serializer(self.get_queryset(), many=True).data})


class StudentEventList(generics.ListAPIView):
    serializer_class = EventSerializer
    pagination_class = None

    def get_queryset(self):
        return Event.objects.filter(date__gte=timezone.localdate()).order_by('date', 'time')

    def list(self, request, *args, **kwargs):
        return Response({'events': self.get_serializer(self.get_queryset(), many=True).data})


class StudentInquiryCreate(generics.GenericAPIView):
    """Submit student interest using POST. Existing student records are staff-only."""
    permission_classes = [permissions.AllowAny]
    serializer_class = StudentInquiryCreateSerializer

    def get(self, request):
        return Response({'detail': 'Use the form below or POST JSON to submit an inquiry.',
                         'courses': reverse('course-list', request=request),
                         'events': reverse('event-list', request=request)})

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        email = values['email'].lower()
        course, event = values['course'], values['event']
        with transaction.atomic():
            student, _ = Student.objects.get_or_create(email=email, defaults={
                'full_name': values['full_name'], 'phone': values['phone'], 'location': values['student_location'],
            })
            # Serialize submissions for this student on PostgreSQL so concurrent
            # retries cannot both pass the rolling 24-hour duplicate check.
            student = Student.objects.select_for_update().get(pk=student.pk)
            recent = Inquiry.objects.filter(student=student, course=course, event=event,
                                            created_at__gte=timezone.now() - timedelta(hours=24)).order_by('-created_at').first()
            if recent:
                return Response({'reference': recent.reference, 'duplicate': True}, status=status.HTTP_200_OK)
            student.full_name = values['full_name']
            student.phone = values['phone']
            student.location = values['student_location']
            student.save(update_fields=['full_name',
                         'phone', 'location', 'updated_at'])
            reference = f"TGM-{timezone.localdate():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
            inquiry = Inquiry.objects.create(
                **{**values, 'student': student, 'email': email, 'reference': reference})
        return Response({'reference': inquiry.reference, 'duplicate': False}, status=status.HTTP_201_CREATED)


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def admin_csrf(request):
    return Response({'csrfToken': get_token(request)})


class AdminLogin(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminLoginSerializer

    def get(self, request):
        return Response({'detail': 'Sign in with a Django staff account. Browser users can also use the Log in link.',
                         'csrf': reverse('admin-csrf', request=request)})

    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, username=serializer.validated_data['username'],
                            password=serializer.validated_data['password'])
        requested_role = serializer.validated_data['role']
        valid_role = bool(user)
        if requested_role == 'Super Admin':
            valid_role = valid_role and user.is_superuser
        elif requested_role == 'Admin':
            valid_role = valid_role and user.is_staff and not user.is_superuser and not user.groups.filter(name='Counsellor').exists()
        elif requested_role == 'Counsellor':
            valid_role = valid_role and user.is_staff and user.groups.filter(name='Counsellor').exists()
        else:
            valid_role = valid_role and not user.is_staff
        if not valid_role:
            return Response({'error': 'Username or password is incorrect, or this account is not an admin.'}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response({'username': user.get_username(), 'role': requested_role, 'full_name': user.first_name, 'email': user.email})


class StaffSignup(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = StaffSignupSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        role = values['role']
        if role == 'Student':
            if not values.get('email') or not values.get('full_name'):
                return Response({'error': 'Full name and email are required for a student account.'}, status=400)
            User = get_user_model()
            if User.objects.filter(username=values['username']).exists() or User.objects.filter(email__iexact=values['email']).exists():
                return Response({'error': 'That username or email is already registered.'}, status=400)
            user = User.objects.create_user(values['username'], email=values['email'], password=values['password'], first_name=values['full_name'])
            login(request, user)
        return Response({'username': user.get_username(), 'role': role, 'full_name': user.first_name, 'email': user.email}, status=201)


class PortalAuthMe(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            role = 'Super Admin'
        elif user.is_staff and user.groups.filter(name='Counsellor').exists():
            role = 'Counsellor'
        elif user.is_staff:
            role = 'Admin'
        else:
            role = 'Student'
        return Response({'username': user.get_username(), 'role': role,
                         'full_name': user.first_name, 'email': user.email})


class PortalLogout(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        logout(request)
        return Response({'ok': True})
        if get_user_model().objects.filter(username=values['username']).exists():
            return Response({'error': 'That username is already in use.'}, status=400)
        if role in ('Admin', 'Counsellor'):
            expected = getattr(settings, 'PORTAL_ORGANISATION_CODE', '')
            saved_org = PortalAccessCode.objects.filter(name='organisation').first()
            valid_org = check_password(values.get('organisation_code', ''), saved_org.code_hash) if saved_org else values.get('organisation_code') == expected
            if not valid_org or not values.get('staff_id'):
                return Response({'error': 'A valid staff ID and organisation code are required.'}, status=403)
        else:
            expected = getattr(settings, 'SUPER_ADMIN_ACCESS_CODE', '')
            saved = PortalAccessCode.objects.filter(name='super_admin').first()
            valid_access = check_password(values.get('access_code', ''), saved.code_hash) if saved else values.get('access_code') == expected
            if not valid_access:
                return Response({'error': 'The Super Admin access code is incorrect.'}, status=403)
        User = get_user_model()
        user = User.objects.create_user(values['username'], password=values['password'])
        if role == 'Super Admin':
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=['is_staff', 'is_superuser'])
        else:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
            if role == 'Counsellor':
                group, _ = Group.objects.get_or_create(name='Counsellor')
                user.groups.add(group)
            StaffProfile.objects.create(user=user, role=role, staff_id=values['staff_id'],
                                        organisation_code_hash=make_password(values['organisation_code']))
        login(request, user)
        return Response({'username': user.get_username(), 'role': role}, status=201)


class StaffAPIView(generics.GenericAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = serializers.Serializer

    def require_catalog_write(self):
        if self.request.user.groups.filter(name='Counsellor').exists() and not self.request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Counsellors have read-only access to courses.')


class AdminLogout(StaffAPIView):
    def post(self, request):
        logout(request)
        return Response({'ok': True})


class AdminMe(StaffAPIView):
    def get(self, request):
        if request.user.is_superuser:
            role = 'Super Admin'
        elif request.user.groups.filter(name='Counsellor').exists():
            role = 'Counsellor'
        else:
            role = 'Admin'
        return Response({'username': request.user.get_username(), 'role': role,
                         'onboarding': {'title': 'Welcome to Student Portal',
                         'message': 'Use the workspace to review student interest, manage the course catalogue and check event demand.'}})


class SuperAdminAccessCode(StaffAPIView):
    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Super Admin access required.'}, status=403)
        code = str(request.data.get('access_code', '')).strip()
        if len(code) < 8:
            return Response({'error': 'The access code must be at least 8 characters.'}, status=400)
        item, _ = PortalAccessCode.objects.get_or_create(name='super_admin')
        item.code_hash = make_password(code)
        item.save(update_fields=['code_hash', 'updated_at'])
        return Response({'ok': True})


class SuperAdminOrganisationCode(StaffAPIView):
    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Super Admin access required.'}, status=403)
        code = str(request.data.get('organisation_code', '')).strip()
        if len(code) < 8:
            return Response({'error': 'The organisation code must be at least 8 characters.'}, status=400)
        item, _ = PortalAccessCode.objects.get_or_create(name='organisation')
        item.code_hash = make_password(code)
        item.save(update_fields=['code_hash', 'updated_at'])
        return Response({'ok': True})


class SuperAdminAPIView(StaffAPIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Super Admin access required.')


class AdminUserManagement(SuperAdminAPIView):
    def get(self, request):
        users = get_user_model().objects.prefetch_related('groups').order_by('username')
        return Response({'users': [{'id': user.id, 'username': user.username, 'email': user.email,
                                    'role': 'Super Admin' if user.is_superuser else ('Counsellor' if user.groups.filter(name='Counsellor').exists() else ('Admin' if user.is_staff else 'Student')),
                                    'active': user.is_active, 'date_joined': user.date_joined.isoformat()} for user in users]})


class AdminStudentList(StaffAPIView):
    def get(self, request):
        students = Student.objects.order_by('-created_at')
        return Response({'students': [{'id': student.id, 'full_name': student.full_name, 'email': student.email,
                                       'phone': student.phone, 'location': student.location,
                                       'inquiries': student.inquiries.count(), 'created_at': student.created_at.isoformat()} for student in students]})


class AdminDashboard(StaffAPIView):
    def get(self, request):
        inquiries = filtered_inquiries(request.query_params).order_by()
        daily = inquiries.annotate(day=TruncDate('created_at')).values(
            'day').annotate(total=Count('id')).order_by('day')
        course_stats = inquiries.values('course_id', 'course__name', 'course__price').annotate(
            total=Count('id'), revenue=Sum(F('course__price'))).order_by('-total', 'course__name', 'course_id')
        event_counts = dict(inquiries.values('event_id').annotate(
            total=Count('id')).values_list('event_id', 'total'))
        events = Event.objects.order_by('date', 'time')
        if request.query_params.get('event'):
            events = events.filter(pk=request.query_params['event'])
        return Response({'total': inquiries.count(),
                         'status': list(inquiries.values('status').annotate(total=Count('id')).order_by('status')),
                         'over_time': [{'date': row['day'].isoformat(), 'total': row['total']} for row in daily],
                         'courses': list(course_stats),
                         'events': [{'id': event.pk, 'name': event.name, 'capacity': event.capacity,
                                     'total': event_counts.get(event.pk, 0)} for event in events],
                         'intakes': list(inquiries.values('intake').annotate(total=Count('id')).order_by('-total', 'intake')),
                         'destinations': list(inquiries.values('destination').annotate(total=Count('id')).order_by('-total', 'destination')),
                         'locations': list(inquiries.values('student_location').annotate(total=Count('id')).order_by('-total', 'student_location'))})


class AdminFilterOptions(StaffAPIView):
    def get(self, request):
        return Response({field: list(Inquiry.objects.order_by(field).values_list(field, flat=True).distinct())
                         for field in ['intake', 'destination', 'student_location']})


class InquiryPagination(PageNumberPagination):
    page_size = 20
    page_query_param = 'page'


class AdminInquiryList(StaffAPIView):
    serializer_class = AdminInquiryListUpdateSerializer

    def get_queryset(self):
        return filtered_inquiries(self.request.query_params)

    def get(self, request):
        qs = self.get_queryset()
        if request.query_params.get('export') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="student-inquiries.csv"'
            writer = csv.writer(response)
            writer.writerow(['Reference', 'Name', 'Email', 'Phone', 'Course',
                            'Programme type', 'Intake', 'Destination country', 'Destination city', 'Student location', 'Event', 'Status', 'Date'])
            for item in qs:
                writer.writerow(map(spreadsheet_safe, [item.reference, item.full_name, item.email, item.phone, item.course.name,
                                                       item.programme_type, item.intake, item.destination, item.destination_city, item.student_location, item.event.name,
                                                       item.status, item.created_at.isoformat()]))
            return response
        paginator = InquiryPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return Response({'results': AdminInquirySerializer(page, many=True).data,
                         'total': qs.count(), 'page': paginator.page.number,
                         'pages': paginator.page.paginator.num_pages})

    def post(self, request):
        values = self.get_serializer(data=request.data)
        values.is_valid(raise_exception=True)
        try:
            inquiry = Inquiry.objects.get(pk=values.validated_data['id'])
        except (Inquiry.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'id': 'Choose a valid inquiry.'})
        serializer = AdminInquiryUpdateSerializer(
            inquiry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'inquiry': AdminInquirySerializer(inquiry).data})


class AdminInquiryDetail(StaffAPIView):
    serializer_class = AdminInquiryUpdateSerializer

    def get_object(self, inquiry_id):
        try:
            return Inquiry.objects.select_related('course', 'event').get(pk=inquiry_id)
        except Inquiry.DoesNotExist:
            raise NotFound('Inquiry not found.')

    def get(self, request, inquiry_id):
        return Response({'inquiry': AdminInquirySerializer(self.get_object(inquiry_id)).data})

    def patch(self, request, inquiry_id):
        item = self.get_object(inquiry_id)
        serializer = self.get_serializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'inquiry': AdminInquirySerializer(item).data})


class AdminCourseList(StaffAPIView):
    serializer_class = CourseSerializer

    def get(self, request):
        return Response({'courses': CourseSerializer(Course.objects.order_by('name'), many=True).data})

    def post(self, request):
        self.require_catalog_write()
        serializer = CourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'course': serializer.data}, status=status.HTTP_201_CREATED)


class AdminCourseDetail(StaffAPIView):
    serializer_class = CourseSerializer

    def get_object(self, course_id):
        try:
            return Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            raise NotFound('Course not found.')

    def get(self, request, course_id):
        return Response({'course': self.get_serializer(self.get_object(course_id)).data})

    def patch(self, request, course_id):
        self.require_catalog_write()
        course = self.get_object(course_id)
        serializer = CourseSerializer(course, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'course': serializer.data})

    def delete(self, request, course_id):
        self.require_catalog_write()
        course = self.get_object(course_id)
        course.active = False
        course.save(update_fields=['active'])
        return Response({'ok': True})


class AdminEventList(StaffAPIView):
    serializer_class = EventSerializer

    def get(self, request):
        return Response({'events': EventSerializer(Event.objects.order_by('date'), many=True).data})

    def post(self, request):
        self.require_catalog_write()
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'event': serializer.data}, status=status.HTTP_201_CREATED)


class AdminEventDetail(StaffAPIView):
    serializer_class = EventSerializer

    def get_object(self, event_id):
        try:
            return Event.objects.get(pk=event_id)
        except Event.DoesNotExist:
            raise NotFound('Event not found.')

    def get(self, request, event_id):
        return Response({'event': self.get_serializer(self.get_object(event_id)).data})

    def patch(self, request, event_id):
        self.require_catalog_write()
        event = self.get_object(event_id)
        serializer = EventSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'event': serializer.data})

    def delete(self, request, event_id):
        self.require_catalog_write()
        event = self.get_object(event_id)
        try:
            event.delete()
        except ProtectedError:
            return Response({'error': 'This event has inquiries and cannot be deleted.'}, status=status.HTTP_409_CONFLICT)
        return Response({'ok': True})
