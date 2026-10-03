from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog

URL = '/api/adminpanel/dashboard/stats/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, **extra)


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', email_verified=True, is_verified=True)
        self.admin.is_staff = True
        self.admin.user_type = 'admin'
        self.admin.save()
        make_user('pending@t.io', '0700000002', email_verified=True)      # awaiting approval
        make_user('noemail@t.io', '0700000003')                           # email not verified
        old = make_user('old@t.io', '0700000004', email_verified=True, is_verified=True)
        old.created_at = timezone.now() - timedelta(days=30)
        old.save()
        AuditLog.objects.create(actor=self.admin, actor_email='admin@t.io', action=AuditLog.Action.USER_APPROVED,
                                target_type='user', target_label='x@t.io')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_counts_and_shape(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['users']['total'], 4)
        self.assertEqual(d['users']['admins'], 1)
        self.assertEqual(d['users']['pending_approval'], 1)
        self.assertEqual(d['users']['unverified_email'], 1)
        self.assertEqual(d['users']['new_this_week'], 3)
        self.assertEqual(d['jobs']['total'], 0)
        self.assertEqual(d['applications']['pending'], 0)

        signups = d['trends']['signups']
        self.assertEqual(len(signups), 14)
        self.assertEqual(signups[-1]['date'], timezone.localdate().isoformat())
        self.assertEqual(sum(day['count'] for day in signups), 3)  # the 30-day-old user is outside the window

        self.assertEqual(len(d['recent_signups']), 4)
        self.assertEqual(d['recent_activity'][0]['action'], 'user.approved')

    def test_non_admin_forbidden(self):
        member = CustomUser.objects.get(email='pending@t.io')
        client = APIClient(); client.force_authenticate(member)
        self.assertEqual(client.get(URL).status_code, 403)
