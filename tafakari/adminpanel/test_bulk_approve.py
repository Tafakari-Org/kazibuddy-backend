import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog

URL = '/api/adminpanel/users/bulk-approve/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, **extra)


@patch('adminpanel.views.send_otp_to_email')
class BulkApproveTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001')
        self.admin.is_staff = True
        self.admin.save()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_approves_eligible_and_reports_skipped(self, mail):
        a = make_user('a@t.io', '0700000002', email_verified=True)
        b = make_user('b@t.io', '0700000003', email_verified=True)
        unverified = make_user('c@t.io', '0700000004', email_verified=False)
        done = make_user('d@t.io', '0700000005', email_verified=True, is_verified=True)
        missing = str(uuid.uuid4())

        r = self.client.post(URL, {'user_ids': [str(a.id), str(b.id), str(unverified.id), str(done.id), missing, str(a.id)]},
                             format='json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual({u['email'] for u in body['approved']}, {'a@t.io', 'b@t.io'})
        reasons = {s['id']: s['reason'] for s in body['skipped']}
        self.assertEqual(reasons[str(unverified.id)], 'Email not verified')
        self.assertEqual(reasons[str(done.id)], 'Already approved')
        self.assertEqual(reasons[missing], 'User not found')

        a.refresh_from_db(); unverified.refresh_from_db()
        self.assertTrue(a.is_verified)
        self.assertFalse(unverified.is_verified)
        self.assertEqual(mail.call_count, 2)
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.Action.USER_APPROVED).count(), 2)

    def test_validation(self, _mail):
        self.assertEqual(self.client.post(URL, {'user_ids': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {}, format='json').status_code, 400)
        too_many = [str(uuid.uuid4()) for _ in range(101)]
        self.assertEqual(self.client.post(URL, {'user_ids': too_many}, format='json').status_code, 400)

    def test_non_admin_forbidden(self, _mail):
        member = make_user('m@t.io', '0700000009', email_verified=True)
        client = APIClient(); client.force_authenticate(member)
        self.assertEqual(client.post(URL, {'user_ids': [str(member.id)]}, format='json').status_code, 403)

    def test_single_approve_still_works(self, _mail):
        u = make_user('s@t.io', '0700000010', email_verified=True)
        r = self.client.post(f'/api/adminpanel/users/{u.id}/approve/')
        self.assertEqual(r.status_code, 200)
        u2 = make_user('s2@t.io', '0700000011', email_verified=False)
        self.assertEqual(self.client.post(f'/api/adminpanel/users/{u2.id}/approve/').status_code, 400)
