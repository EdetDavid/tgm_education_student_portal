from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portal.models import StaffProfile


class DjangoAdminUserDeletionTests(TestCase):
    def test_users_are_assigned_a_portal_role_group(self):
        User = get_user_model()
        student = User.objects.create_user(username='role-student', password='TestOnly934!')
        admin = User.objects.create_user(username='role-admin', password='TestOnly934!', is_staff=True)
        super_admin = User.objects.create_superuser(
            username='role-super-admin', email='role-super-admin@example.com', password='TestOnly934!'
        )

        self.assertQuerySetEqual(student.groups.order_by('name'), ['Student'], transform=lambda group: group.name)
        self.assertQuerySetEqual(admin.groups.order_by('name'), ['Admin'], transform=lambda group: group.name)
        self.assertQuerySetEqual(super_admin.groups.order_by('name'), ['Super Admin'], transform=lambda group: group.name)

    def test_bulk_delete_removes_staff_user_and_profile(self):
        admin = get_user_model().objects.create_superuser(
            username='site-admin', email='site-admin@example.com', password='TestOnly934!'
        )
        staff = get_user_model().objects.create_user(
            username='portal-admin', password='TestOnly934!', is_staff=True
        )
        profile = StaffProfile.objects.create(
            user=staff, role='Admin', staff_id='TGM-DELETE-001', organisation_code_hash='test-hash'
        )
        self.client.force_login(admin)
        url = reverse('admin:auth_user_changelist')
        selection = {
            'action': 'delete_selected',
            '_selected_action': [str(staff.pk)],
            'index': '0',
        }

        confirmation = self.client.post(url, selection)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, 'Are you sure')

        deleted = self.client.post(url, selection | {'post': 'yes'})
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=staff.pk).exists())
        self.assertFalse(StaffProfile.objects.filter(pk=profile.pk).exists())

