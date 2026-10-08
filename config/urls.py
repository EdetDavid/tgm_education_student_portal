from django.urls import include, path
from portal import views
from django.contrib import admin


urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/', views.ApiRoot.as_view(), name='api-root'),
    path('api/auth/', include('rest_framework.urls')),
    path('api/courses/', views.StudentCourseList.as_view(), name='course-list'),
    path('api/events/', views.StudentEventList.as_view(), name='event-list'),
    path('api/inquiries/', views.StudentInquiryCreate.as_view(), name='inquiry-create'),
    path('api/admin/csrf/', views.admin_csrf, name='admin-csrf'),
    path('api/admin/login/', views.AdminLogin.as_view(), name='admin-login'),
    path('api/auth/signup/', views.StaffSignup.as_view(), name='staff-signup'),
    path('api/auth/me/', views.PortalAuthMe.as_view(), name='portal-auth-me'),
    path('api/auth/logout/', views.PortalLogout.as_view(), name='portal-auth-logout'),
    path('api/admin/access-code/', views.SuperAdminAccessCode.as_view(), name='super-admin-access-code'),
    path('api/admin/organisation-code/', views.SuperAdminOrganisationCode.as_view(), name='super-admin-organisation-code'),
    path('api/admin/users/', views.AdminUserManagement.as_view(), name='admin-users'),
    path('api/admin/students/', views.AdminStudentList.as_view(), name='admin-students'),
    path('api/admin/logout/', views.AdminLogout.as_view()),
    path('api/admin/me/', views.AdminMe.as_view()),
    path('api/admin/dashboard/', views.AdminDashboard.as_view(), name='admin-dashboard'),
    path('api/admin/filters/', views.AdminFilterOptions.as_view(), name='admin-filters'),
    path('api/admin/inquiries/', views.AdminInquiryList.as_view(), name='admin-inquiries'),
    path('api/admin/inquiries/<int:inquiry_id>/', views.AdminInquiryDetail.as_view()),
    path('api/admin/courses/', views.AdminCourseList.as_view(), name='admin-courses'),
    path('api/admin/courses/<int:course_id>/', views.AdminCourseDetail.as_view()),
    path('api/admin/events/', views.AdminEventList.as_view(), name='admin-events'),
    path('api/admin/events/<int:event_id>/', views.AdminEventDetail.as_view()),
]
