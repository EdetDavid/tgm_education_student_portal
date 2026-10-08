from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from portal.models import Course, Event, Inquiry, Student


class PortalApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True, HTTP_HOST='localhost')
        self.course = Course.objects.create(name='Computer Science', level='Undergraduate', price='18000.00',
                                            location='London', intakes=['January', 'May', 'September'])
        self.event = Event.objects.create(name='Exhibition', city='Lagos', venue='Exhibition Hall',
                                          date=timezone.localdate() + timedelta(days=14), time='10:00', capacity=120)
        self.staff = get_user_model().objects.create_user(username='staff', password='TestOnly934!', is_staff=True)

    def payload(self, **extra):
        data = {'full_name': 'Amara Okafor', 'email': 'amara@example.com', 'phone': '+234 801 234 5678',
                'course_id': self.course.pk, 'intake': f'January {timezone.localdate().year + 1}',
                'destination': 'United Kingdom', 'student_location': 'Lagos, Nigeria', 'event_id': self.event.pk,
                'message': 'Can I ask about accommodation?'}
        return data | extra

    def csrf(self):
        response = self.client.get('/api/admin/csrf/')
        self.assertEqual(response.status_code, 200)
        return response.json()['csrfToken']

    def sign_in(self):
        response = self.client.post('/api/admin/login/', {'username': 'staff', 'password': 'TestOnly934!'},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)

    def test_catalog_only_shows_active_courses_and_upcoming_events(self):
        self.course.active = False
        self.course.save()
        self.event.date = timezone.localdate() - timedelta(days=1)
        self.event.save()
        self.assertEqual(self.client.get('/api/courses/').json()['courses'], [])
        self.assertEqual(self.client.get('/api/events/').json()['events'], [])

    def test_student_form_receives_the_same_intakes_the_server_accepts(self):
        course = self.client.get('/api/courses/').json()['courses'][0]
        self.assertIn(self.payload()['intake'], course['intake_options'])
        response = self.client.post('/api/inquiries/', self.payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['reference'].startswith('TGM-'))
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_duplicate_submission_reuses_reference_without_another_record(self):
        first = self.client.post('/api/inquiries/', self.payload(), format='json')
        repeat = self.client.post('/api/inquiries/', self.payload(email=' AMARA@example.com '), format='json')
        self.assertEqual(repeat.status_code, 200)
        self.assertTrue(repeat.json()['duplicate'])
        self.assertEqual(first.json()['reference'], repeat.json()['reference'])
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_phone_intake_and_event_validation(self):
        for fields in ({'phone': '-------'}, {'phone': '+1234567890123456'}, {'intake': 'Unknown intake'},
                       {'student_location': 'Lagos'}, {'student_location': 'Lagos, '},
                       {'full_name': '  '}, {'message': 'x' * 1001}, {'event_id': 99999}):
            with self.subTest(fields=fields):
                response = self.client.post('/api/inquiries/', self.payload(**fields), format='json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)

    def test_login_requires_a_csrf_token_and_staff_credentials(self):
        response = self.client.post('/api/admin/login/', {'username': 'staff', 'password': 'TestOnly934!'}, format='json')
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/api/admin/login/', {'username': 'staff', 'password': 'incorrect'},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 401)
        self.sign_in()
        self.assertEqual(self.client.get('/api/admin/me/').json()['username'], 'staff')

    def test_anonymous_and_nonstaff_users_cannot_access_admin(self):
        self.assertEqual(self.client.get('/api/admin/dashboard/').status_code, 403)
        student = get_user_model().objects.create_user(username='student', password='TestOnly934!')
        self.client.force_login(student)
        self.assertEqual(self.client.get('/api/admin/courses/').status_code, 403)

    def test_student_submission_also_works_during_admin_session(self):
        self.sign_in()
        response = self.client.post('/api/inquiries/', self.payload(), format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 201)

    def test_admin_inquiry_search_update_export_and_dashboard(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        self.sign_in()
        item = Inquiry.objects.get()
        response = self.client.post('/api/admin/inquiries/', {'id': item.pk, 'status': 'Contacted', 'internal_notes': 'Called student'},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['inquiry']['status'], 'Contacted')
        results = self.client.get('/api/admin/inquiries/?q=AMARA&status=Contacted').json()
        self.assertEqual(results['total'], 1)
        self.assertEqual(results['results'][0]['internal_notes'], 'Called student')
        self.assertEqual(self.client.get('/api/admin/inquiries/?course=invalid').status_code, 400)
        export = self.client.get('/api/admin/inquiries/?export=csv&status=Contacted')
        self.assertContains(export, item.reference)
        self.assertEqual(self.client.get('/api/admin/dashboard/').json()['total'], 1)

    def test_course_management_and_deactivation_preserve_inquiry_relation(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        self.sign_in()
        response = self.client.patch(f'/api/admin/courses/{self.course.pk}/', {'name': 'Updated Computer Science'},
                                     format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/admin/inquiries/').json()['results'][0]['course'], 'Updated Computer Science')
        response = self.client.delete(f'/api/admin/courses/{self.course.pk}/', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/courses/').json()['courses'], [])
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_course_and_event_writes_validate_data(self):
        self.sign_in()
        response = self.client.post('/api/admin/courses/', {'name': 'New course', 'level': 'Undergraduate', 'price': '-1',
                                                           'location': 'London', 'intakes': ['Invalid']},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/admin/events/', {'name': 'New event', 'city': 'Abuja', 'venue': 'Hall',
                                                          'date': (timezone.localdate() + timedelta(days=30)).isoformat(),
                                                          'time': '10:00', 'capacity': 120},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 2)

    def test_api_root_and_public_request_forms_are_browsable(self):
        root = self.client.get('/api/')
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()['courses'], 'http://localhost/api/courses/')
        for url in ['/api/', '/api/courses/', '/api/events/', '/api/inquiries/', '/api/admin/login/']:
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_ACCEPT='text/html')
                self.assertEqual(response.status_code, 200)
                self.assertIn('text/html', response['Content-Type'])
                self.assertContains(response, 'rest_framework/css/bootstrap.min.css')
        form = self.client.get('/api/inquiries/', HTTP_ACCEPT='text/html')
        self.assertContains(form, 'name="full_name"')
        self.assertEqual(self.client.get('/api/auth/login/').status_code, 200)
        self.client.post('/api/inquiries/', self.payload(), format='json')
        self.assertNotContains(self.client.get('/api/inquiries/'), 'amara@example.com')

    def test_staff_api_forms_detail_reads_and_patch_requests(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        item = Inquiry.objects.get()
        urls = ['/api/admin/dashboard/', '/api/admin/filters/', '/api/admin/inquiries/',
                f'/api/admin/inquiries/{item.pk}/', '/api/admin/courses/',
                f'/api/admin/courses/{self.course.pk}/', '/api/admin/events/',
                f'/api/admin/events/{self.event.pk}/']
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.sign_in()
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, HTTP_ACCEPT='text/html').status_code, 200)
        self.assertContains(self.client.get('/api/admin/courses/', HTTP_ACCEPT='text/html'), 'name="name"')
        self.assertEqual(self.client.get(f'/api/admin/courses/{self.course.pk}/').json()['course']['name'], self.course.name)
        self.assertEqual(self.client.get(f'/api/admin/events/{self.event.pk}/').json()['event']['name'], self.event.name)
        response = self.client.patch(f'/api/admin/inquiries/{item.pk}/', {'status': 'Converted', 'internal_notes': 'Enrolled'},
                                     format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['inquiry']['status'], 'Converted')
        response = self.client.patch(f'/api/admin/events/{self.event.pk}/', {'venue': 'New Hall', 'capacity': 180},
                                     format='json', HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['event']['capacity'], 180)
        self.assertEqual(self.client.get('/api/admin/logout/', HTTP_ACCEPT='text/html').status_code, 405)

    def test_dashboard_table_and_export_use_the_same_filters(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        self.client.post('/api/inquiries/', self.payload(full_name='Zara Musa', email='zara@example.com',
                                                       student_location='Abuja, Nigeria', destination='Canada'), format='json')
        self.sign_in()
        query = f'course={self.course.pk}&event={self.event.pk}&status=New&student_location=lagos&destination=United%20Kingdom'
        self.assertEqual(self.client.get('/api/admin/inquiries/?' + query).json()['total'], 1)
        stats = self.client.get('/api/admin/dashboard/?' + query).json()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['events'][0]['total'], 1)
        self.assertEqual(stats['courses'][0]['revenue'], 18000)
        self.assertEqual(stats['locations'][0]['student_location'], 'Lagos, Nigeria')
        export = self.client.get('/api/admin/inquiries/?export=csv&' + query)
        self.assertContains(export, 'amara@example.com')
        self.assertNotContains(export, 'zara@example.com')
        records = self.client.get('/api/admin/inquiries/?ordering=-full_name').json()['results']
        self.assertEqual(records[0]['full_name'], 'Zara Musa')
        self.assertEqual(self.client.get('/api/admin/inquiries/?ordering=not-a-field').status_code, 400)
        self.assertEqual(self.client.get('/api/admin/dashboard/?course=invalid').status_code, 400)
        self.assertEqual(self.client.get('/api/admin/filters/').json()['destination'], ['Canada', 'United Kingdom'])

    def test_course_can_be_reactivated_and_missing_details_return_404(self):
        self.sign_in()
        for active in [False, True]:
            response = self.client.patch(f'/api/admin/courses/{self.course.pk}/', {'active': active},
                                         format='json', HTTP_X_CSRFTOKEN=self.csrf())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(self.client.get('/api/courses/').json()['courses']), int(active))
        for resource in ['courses', 'events', 'inquiries']:
            self.assertEqual(self.client.get(f'/api/admin/{resource}/99999/').status_code, 404)

    def test_course_search_and_filters_run_on_the_server(self):
        another = Course.objects.create(name='Business Management', level='Postgraduate', price=12000,
                                       location='Manchester', intakes=['September'])
        Course.objects.create(name='Inactive Computer Course', level='Undergraduate', price=10000,
                              location='London', intakes=['January'], active=False)
        for query in ['q=puter', 'q=LONDON', 'q=undergrad']:
            self.assertEqual([row['id'] for row in self.client.get('/api/courses/?' + query).json()['courses']], [self.course.pk])
        results = self.client.get('/api/courses/?q=management&level=postgraduate&location=manchester').json()['courses']
        self.assertEqual(results[0]['id'], another.pk)
        self.assertEqual(self.client.get('/api/courses/?q=nothing-matches').json()['courses'], [])
        self.assertEqual(self.client.get('/api/courses/?q=' + 'x' * 201).status_code, 400)

    def test_student_identity_is_reused_without_rewriting_inquiry_snapshots(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        first = Inquiry.objects.get()
        another = Course.objects.create(name='Data Science', level='Postgraduate', price=22000,
                                       location='London', intakes=['January'])
        response = self.client.post('/api/inquiries/', self.payload(email='AMARA@example.com', course_id=another.pk,
                                                                   full_name='Amara Updated', phone='+234 801 234 9999'), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Student.objects.count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.full_name, 'Amara Okafor')
        self.assertEqual(first.student.full_name, 'Amara Updated')
        self.assertEqual(first.student.inquiries.count(), 2)

    def test_duplicate_window_expires_and_submission_creates_a_new_reference(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        first = Inquiry.objects.get()
        Inquiry.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(hours=25))
        response = self.client.post('/api/inquiries/', self.payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()['reference'], first.reference)
        self.assertEqual(Student.objects.count(), 1)

    def test_revenue_keeps_distinct_courses_with_the_same_name_separate(self):
        self.client.post('/api/inquiries/', self.payload(), format='json')
        another = Course.objects.create(name=self.course.name, level='Postgraduate', price=22000,
                                       location='Manchester', intakes=['January'])
        self.client.post('/api/inquiries/', self.payload(email='other@example.com', course_id=another.pk), format='json')
        self.sign_in()
        courses = self.client.get('/api/admin/dashboard/').json()['courses']
        self.assertEqual(len(courses), 2)
        self.assertEqual({row['course_id'] for row in courses}, {self.course.pk, another.pk})
        self.assertEqual(sum(row['revenue'] for row in courses), 40000)

    def test_pagination_partial_phone_reference_and_location_filters(self):
        for index in range(25):
            Inquiry.objects.create(full_name=f'Student {index:02d}', email=f's{index}@example.com', phone='+234 801 234 5678',
                                   course=self.course, event=self.event, intake='January 2027', destination='Canada',
                                   student_location='Abuja, Nigeria', reference=f'TEST-{index:04d}')
        self.sign_in()
        first = self.client.get('/api/admin/inquiries/?ordering=full_name').json()
        second = self.client.get('/api/admin/inquiries/?ordering=full_name&page=2').json()
        self.assertEqual(first['total'], 25)
        self.assertEqual(first['pages'], 2)
        self.assertEqual(len(first['results']), 20)
        self.assertEqual(len(second['results']), 5)
        self.assertEqual(second['results'][0]['full_name'], 'Student 20')
        self.assertEqual(self.client.get('/api/admin/inquiries/?q=234%205678').json()['total'], 25)
        self.assertEqual(self.client.get('/api/admin/inquiries/?q=TEST-0024&student_location=abu').json()['total'], 1)

    def test_csv_export_escapes_formula_like_student_text(self):
        self.client.post('/api/inquiries/', self.payload(full_name='=1+1'), format='json')
        self.sign_in()
        export = self.client.get('/api/admin/inquiries/?export=csv')
        self.assertContains(export, "'=1+1")
        self.assertContains(export, "'+234")
