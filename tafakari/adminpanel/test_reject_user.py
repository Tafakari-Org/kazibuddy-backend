from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog
from utils.views import build_account_rejected_email


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='Jane Wanjiru',
                                          phone_number=phone, **extra)


class RejectUserTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001')
        self.admin.is_staff = True
        self.admin.save()
        self.user = make_user('jane@t.io', '0700000002', email_verified=True)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.url = f'/api/adminpanel/users/{self.user.id}/reject/'

    @patch('adminpanel.views.send_account_rejected_email')
    def test_reject_flow(self, mail):
        r = self.admin_client.post(self.url, {'reasons': ['documents_unclear', 'name_mismatch'],
                                              'note': 'Your certificate photo is blurry.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.rejected_at)
        self.assertEqual(self.user.rejection_reasons, ['documents_unclear', 'name_mismatch'])

        # Email gets readable reasons, fixes and the note
        user_arg, reasons, fixes, note = mail.call_args.args
        self.assertEqual(user_arg, self.user)
        self.assertIn('Your documents were unclear or hard to read', reasons)
        self.assertEqual(len(fixes), 2)
        self.assertEqual(note, 'Your certificate photo is blurry.')

        # Audit trail
        log = AuditLog.objects.get(action=AuditLog.Action.USER_REJECTED)
        self.assertEqual(log.target_label, 'jane@t.io')

        # Leaves the pending queue, shows under ?status=rejected with readable reasons
        pending = self.admin_client.get('/api/adminpanel/users/pending/').json()['results']['data']
        self.assertNotIn(str(self.user.id), [u['user_id'] for u in pending])
        rejected = self.admin_client.get('/api/adminpanel/users/pending/?status=rejected').json()['results']['data']
        self.assertEqual(rejected[0]['rejection_reasons'][1], 'The name on your documents does not match your account')

        # User sees it on their dashboard and can ask for another review
        user_client = APIClient()
        user_client.force_authenticate(self.user)
        rej = user_client.get('/api/accounts/me/dashboard/').json()['account']['rejection']
        self.assertEqual(rej['note'], 'Your certificate photo is blurry.')
        self.assertEqual(user_client.post('/api/accounts/me/request-review/').status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.rejected_at)
        pending = self.admin_client.get('/api/adminpanel/users/pending/').json()['results']['data']
        self.assertIn(str(self.user.id), [u['user_id'] for u in pending])

    @patch('adminpanel.views.send_otp_to_email')
    @patch('adminpanel.views.send_account_rejected_email')
    def test_approving_clears_rejection(self, _mail, _otp):
        self.admin_client.post(self.url, {'reasons': ['documents_missing']}, format='json')
        self.admin_client.post(f'/api/adminpanel/users/{self.user.id}/approve/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertIsNone(self.user.rejected_at)
        self.assertEqual(self.user.rejection_reasons, [])

    @patch('adminpanel.views.send_account_rejected_email')
    def test_validation(self, _mail):
        self.assertEqual(self.admin_client.post(self.url, {'reasons': []}, format='json').status_code, 400)
        self.assertEqual(self.admin_client.post(self.url, {'reasons': ['nope']}, format='json').status_code, 400)
        self.assertEqual(self.admin_client.post(self.url, {'reasons': ['other']}, format='json').status_code, 400)
        member = APIClient(); member.force_authenticate(self.user)
        self.assertEqual(member.post(self.url, {'reasons': ['documents_missing']}, format='json').status_code, 403)
        self.user.is_verified = True; self.user.save()
        self.assertEqual(self.admin_client.post(self.url, {'reasons': ['documents_missing']}, format='json').status_code, 400)

    def test_email_renders(self):
        subject, html = build_account_rejected_email(
            self.user, ['Your documents were unclear or hard to read'],
            ['Upload clear, well-lit scans or photos (PDF or image, up to 5 MB each).'], 'Blurry <b>photo</b>.')
        self.assertEqual(subject, 'Update on your KaziBuddy account')
        self.assertIn('Hello, Jane Wanjiru', html)
        self.assertIn('Your documents were unclear or hard to read', html)
        self.assertIn('Request review again', html)
        self.assertIn('/profile', html)
        self.assertIn('Blurry &lt;b&gt;photo&lt;/b&gt;.', html)  # note is escaped
