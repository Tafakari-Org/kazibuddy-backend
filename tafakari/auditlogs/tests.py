from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from .models import AuditLog


def make_user(email, phone, staff=False, **extra):
    user = CustomUser.objects.create_user(
        email=email, password='Passw0rd!x', full_name=email.split('@')[0].title(), phone_number=phone, **extra
    )
    if staff:
        user.is_staff = True
        user.user_type = 'admin'
        user.save()
    return user


@patch('adminpanel.views.send_otp_to_email')
class AuditLogTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', staff=True)
        self.member = make_user('member@t.io', '0700000002', email_verified=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_approving_user_is_logged(self, _mail):
        r = self.client.post(f'/api/adminpanel/users/{self.member.id}/approve/')
        self.assertEqual(r.status_code, 200)
        log = AuditLog.objects.get()
        self.assertEqual(log.action, AuditLog.Action.USER_APPROVED)
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.actor_email, 'admin@t.io')
        self.assertEqual(log.target_id, str(self.member.id))
        self.assertEqual(log.target_label, 'member@t.io')

    def test_deleting_user_is_logged_and_survives_deletion(self, _mail):
        r = self.client.delete('/api/adminpanel/delete-user/member@t.io/')
        self.assertEqual(r.status_code, 200)
        log = AuditLog.objects.get(action=AuditLog.Action.USER_DELETED)
        self.assertEqual(log.target_label, 'member@t.io')
        self.assertEqual(log.details['full_name'], 'Member')

    def test_role_change_records_before_and_after(self, _mail):
        self.client.patch(f'/api/adminpanel/users/{self.member.id}/change-role/', {'user_type': 'admin'}, format='json')
        log = AuditLog.objects.get(action=AuditLog.Action.USER_ROLE_CHANGED)
        self.assertEqual(log.details['from'], 'user')
        self.assertEqual(log.details['to'], 'admin')

    def test_list_search_filter_and_pagination(self, _mail):
        for i in range(25):
            AuditLog.objects.create(actor=self.admin, actor_email='admin@t.io', actor_name='Admin',
                                    action=AuditLog.Action.JOB_APPROVED, target_type='job', target_label=f'Plumber {i}')
        AuditLog.objects.create(actor=self.admin, actor_email='admin@t.io', action=AuditLog.Action.USER_DELETED,
                                target_type='user', target_label='gone@t.io')

        r = self.client.get('/api/adminpanel/audit-logs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 26)
        self.assertEqual(len(r.json()['results']), 20)
        self.assertEqual(r.json()['total_pages'], 2)

        r = self.client.get('/api/adminpanel/audit-logs/', {'page': 2})
        self.assertEqual(len(r.json()['results']), 6)

        r = self.client.get('/api/adminpanel/audit-logs/', {'action': 'user.deleted'})
        self.assertEqual(r.json()['count'], 1)
        self.assertEqual(r.json()['results'][0]['action_label'], 'Deleted user')

        r = self.client.get('/api/adminpanel/audit-logs/', {'search': 'plumber 1'})
        self.assertEqual(r.json()['count'], 11)  # Plumber 1, 10-19

        r = self.client.get('/api/adminpanel/audit-logs/', {'target_type': 'user', 'actor': str(self.admin.id)})
        self.assertEqual(r.json()['count'], 1)

        r = self.client.get('/api/adminpanel/audit-logs/', {'date_from': '2000-01-01', 'date_to': '2000-01-02'})
        self.assertEqual(r.json()['count'], 0)

    def test_filters_endpoint(self, _mail):
        AuditLog.objects.create(actor=self.admin, actor_email='admin@t.io', actor_name='Admin',
                                action=AuditLog.Action.JOB_APPROVED, target_type='job')
        r = self.client.get('/api/adminpanel/audit-logs/filters/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['actors'], [{'id': str(self.admin.id), 'name': 'Admin', 'email': 'admin@t.io'}])
        self.assertIn({'value': 'user.approved', 'label': 'Approved user'}, r.json()['actions'])

    def test_non_admin_cannot_read_logs(self, _mail):
        client = APIClient()
        client.force_authenticate(self.member)
        self.assertEqual(client.get('/api/adminpanel/audit-logs/').status_code, 403)
        self.assertEqual(client.get('/api/adminpanel/audit-logs/filters/').status_code, 403)
