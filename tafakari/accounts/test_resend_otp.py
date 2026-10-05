from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, OTPVerification
from utils.views import generate_otp

URL = '/api/accounts/resend-otp/'


@patch('accounts.otp_resend.schedule_unverified_cleanup')
@patch('accounts.otp_resend.send_otp_to_email')
class ResendOTPTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(email='new@t.io', password='Passw0rd!x', full_name='New User',
                                                   phone_number='0700000081')
        self.client = APIClient()

    def _age_otps(self, seconds):
        OTPVerification.objects.update(created_at=timezone.now() - timedelta(seconds=seconds))

    def test_resend_after_expiry_issues_new_working_code(self, send, cleanup):
        old_code = generate_otp(self.user, 'registration')
        OTPVerification.objects.update(created_at=timezone.now() - timedelta(minutes=6),
                                       expires_at=timezone.now() - timedelta(minutes=1))

        r = self.client.post(URL, {'user_id': str(self.user.id), 'email': 'NEW@t.io'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('otp_expires_at', r.json())
        new_code = send.call_args.args[1]
        cleanup.assert_called_once()

        verify = lambda code: self.client.post('/api/accounts/verify-email/', {
            'user_id': str(self.user.id), 'otp_code': code, 'otp_type': 'registration'}, format='json')
        if new_code != old_code:
            self.assertEqual(verify(old_code).status_code, 400)
        self.assertEqual(verify(new_code).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_resend_invalidates_unexpired_older_code(self, send, cleanup):
        generate_otp(self.user, 'registration')
        self._age_otps(90)
        self.client.post(URL, {'user_id': str(self.user.id), 'email': 'new@t.io'}, format='json')
        live = OTPVerification.objects.filter(expires_at__gt=timezone.now())
        self.assertEqual(live.count(), 1)

    def test_cooldown(self, send, cleanup):
        generate_otp(self.user, 'registration')
        r = self.client.post(URL, {'user_id': str(self.user.id), 'email': 'new@t.io'}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()['code'], 'cooldown')
        send.assert_not_called()

    def test_hourly_limit(self, send, cleanup):
        for _ in range(5):
            generate_otp(self.user, 'registration')
        self._age_otps(120)
        r = self.client.post(URL, {'user_id': str(self.user.id), 'email': 'new@t.io'}, format='json')
        self.assertEqual(r.json()['code'], 'too_many')

    def test_already_verified(self, send, cleanup):
        self.user.email_verified = True; self.user.save()
        r = self.client.post(URL, {'user_id': str(self.user.id), 'email': 'new@t.io'}, format='json')
        self.assertEqual(r.json()['code'], 'already_verified')

    def test_wrong_email_or_deleted_signup(self, send, cleanup):
        r = self.client.post(URL, {'user_id': str(self.user.id), 'email': 'other@t.io'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['code'], 'signup_expired')
        r = self.client.post(URL, {'user_id': 'not-a-uuid', 'email': 'new@t.io'}, format='json')
        self.assertEqual(r.status_code, 404)
        send.assert_not_called()


class RegistrationEmailLinkTests(TestCase):
    @patch('utils.views.send_email_async')
    def test_email_contains_verify_link(self, send_async):
        from utils.views import send_otp_to_email
        user = CustomUser.objects.create_user(email='new@t.io', password='Passw0rd!x', full_name='New User',
                                              phone_number='0700000082')
        send_otp_to_email(user, '123456', 'registration')
        html = send_async.call_args.args[1]
        self.assertIn('/auth/verify-email?userId=', html)
        self.assertIn('code=123456', html)
        self.assertIn('Verify my email', html)
