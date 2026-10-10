from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from adminpanel.models import FooterSettings
from utils.views import SUPPORT_EMAIL

URL = '/api/accounts/login/'
PASSWORD = 'Passw0rd!x'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password=PASSWORD, full_name='Jane Wanjiru',
                                          phone_number=phone, **extra)


class LoginRefusalTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, email, password=PASSWORD):
        return self.client.post(URL, {'identifier': email, 'password': password}, format='json')

    def test_approved_user_logs_in(self):
        make_user('ok@t.io', '0700000001', email_verified=True, is_verified=True)
        r = self.login('ok@t.io')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('tokens', r.json())

    def test_unverified_email(self):
        make_user('new@t.io', '0700000002')
        r = self.login('new@t.io')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'email_unverified')

    def test_pending_approval(self):
        make_user('wait@t.io', '0700000003', email_verified=True)
        r = self.login('wait@t.io')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'pending_approval')
        self.assertNotIn('rejection', r.json())

    def test_rejected_user_gets_reasons_and_contact(self):
        make_user('no@t.io', '0700000004', email_verified=True, rejected_at=timezone.now(),
                  rejection_reasons=['documents_unclear'], rejection_note='Photo is blurry')
        r = self.login('no@t.io')
        self.assertEqual(r.status_code, 403)
        d = r.json()
        self.assertEqual(d['code'], 'account_rejected')
        self.assertEqual(d['rejection']['reasons'], ['Your documents were unclear or hard to read'])
        self.assertEqual(d['rejection']['note'], 'Photo is blurry')
        self.assertEqual(d['rejection']['support_email'], SUPPORT_EMAIL)
        self.assertNotIn('tokens', d)

    def test_contact_email_follows_footer_settings(self):
        FooterSettings.objects.update_or_create(pk=1, defaults={'email': 'help@kazibuddy.co.ke'})
        make_user('no@t.io', '0700000005', email_verified=True, rejected_at=timezone.now())
        self.assertEqual(self.login('no@t.io').json()['rejection']['support_email'], 'help@kazibuddy.co.ke')

    def test_wrong_password_reveals_nothing_about_rejection(self):
        make_user('no@t.io', '0700000006', email_verified=True, rejected_at=timezone.now(),
                  rejection_reasons=['documents_unclear'])
        r = self.login('no@t.io', 'wrong-password')
        self.assertEqual(r.status_code, 401)
        self.assertNotIn('rejection', r.json())
        self.assertNotIn('documents', r.content.decode())
