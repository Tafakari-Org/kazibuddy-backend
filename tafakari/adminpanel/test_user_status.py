from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog
from utils.views import build_account_approved_email

URL = '/api/adminpanel/all-users/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0].title(),
                                          phone_number=phone, **extra)


class AllUsersStatusTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', email_verified=True, is_verified=True)
        self.admin.is_staff = True
        self.admin.save()
        make_user('approved@t.io', '0700000002', email_verified=True, is_verified=True)
        make_user('pending@t.io', '0700000003', email_verified=True)
        make_user('unverified@t.io', '0700000004')
        self.rejected = make_user('rejected@t.io', '0700000005', email_verified=True,
                                  rejected_at=timezone.now(), rejection_reasons=['documents_unclear'],
                                  rejection_note='Blurry photo')
        make_user('off@t.io', '0700000006', email_verified=True, is_verified=True, is_active=False)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def by_email(self, r):
        return {u['email']: u for u in r.json()['results']}

    def test_each_user_has_a_status(self):
        users = self.by_email(self.client.get(URL))
        self.assertEqual({e: u['status'] for e, u in users.items()}, {
            'admin@t.io': 'approved', 'approved@t.io': 'approved', 'pending@t.io': 'pending',
            'unverified@t.io': 'unverified', 'rejected@t.io': 'rejected', 'off@t.io': 'deactivated',
        })
        rejected = users['rejected@t.io']
        self.assertEqual(rejected['rejection_reasons'], ['Your documents were unclear or hard to read'])
        self.assertEqual(rejected['rejection_note'], 'Blurry photo')
        self.assertIsNotNone(rejected['rejected_at'])
        self.assertEqual(users['pending@t.io']['rejection_reasons'], [])

    def test_status_filter_and_counts(self):
        r = self.client.get(URL, {'status': 'rejected'})
        self.assertEqual(list(self.by_email(r)), ['rejected@t.io'])
        self.assertEqual(r.json()['status_counts'], {
            'deactivated': 1, 'approved': 2, 'rejected': 1, 'pending': 1, 'unverified': 1,
        })
        self.assertEqual(self.client.get(URL, {'status': 'bogus'}).status_code, 400)

    def test_counts_follow_search(self):
        counts = self.client.get(URL, {'search': 'rejected'}).json()['status_counts']
        self.assertEqual(counts['rejected'], 1)
        self.assertEqual(counts['approved'], 0)

    @patch('adminpanel.views.send_account_approved_email')
    def test_approving_rejected_user_clears_rejection_and_emails_them(self, mail):
        r = self.client.post(f'/api/adminpanel/users/{self.rejected.id}/approve/')
        self.assertEqual(r.status_code, 200, r.content)
        self.rejected.refresh_from_db()
        self.assertTrue(self.rejected.is_verified)
        self.assertIsNone(self.rejected.rejected_at)
        self.assertEqual(self.rejected.rejection_reasons, [])
        self.assertEqual(mail.call_args.args[0], self.rejected)
        self.assertTrue(mail.call_args.kwargs['after_review'])
        log = AuditLog.objects.get(action=AuditLog.Action.USER_APPROVED)
        self.assertTrue(log.details['previously_rejected'])
        self.assertEqual(self.by_email(self.client.get(URL))['rejected@t.io']['status'], 'approved')

    @patch('adminpanel.views.send_account_approved_email')
    def test_first_time_approval_is_not_marked_after_review(self, mail):
        pending = CustomUser.objects.get(email='pending@t.io')
        self.client.post(f'/api/adminpanel/users/{pending.id}/approve/')
        self.assertFalse(mail.call_args.kwargs['after_review'])
        self.assertNotIn('previously_rejected', AuditLog.objects.get(action=AuditLog.Action.USER_APPROVED).details)

    def test_after_review_email_wording(self):
        _, html = build_account_approved_email(self.rejected, after_review=True)
        self.assertIn('following a second review', html)
        _, html = build_account_approved_email(self.rejected)
        self.assertNotIn('second review', html)
