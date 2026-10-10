from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog

URL = '/api/accounts/me/change-password/'
OLD = 'OldPassw0rd!x'
NEW = 'Fresh-Passw0rd!42'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password=OLD, full_name='Jane Wanjiru',
                                          phone_number=phone, email_verified=True, is_verified=True, **extra)


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.user = make_user('jane@t.io', '0700000001')
        self.admin = make_user('admin@t.io', '0700000002')
        self.admin.is_staff = True
        self.admin.user_type = 'admin'
        self.admin.save()
        self.client = APIClient()

    def change(self, user, current=OLD, new=NEW):
        self.client.force_authenticate(user)
        return self.client.post(URL, {'current_password': current, 'new_password': new}, format='json')

    def test_requires_login(self):
        self.assertEqual(self.client.post(URL, {}, format='json').status_code, 401)

    def test_user_changes_password(self):
        r = self.change(self.user)
        self.assertEqual(r.status_code, 200, r.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW))
        self.assertFalse(self.user.check_password(OLD))
        # Regular users' password changes are not audited.
        self.assertFalse(AuditLog.objects.exists())

    def test_wrong_current_password(self):
        r = self.change(self.user, current='nope')
        self.assertEqual(r.status_code, 400)
        self.assertIn('current_password', r.json()['stack'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))

    def test_weak_or_unchanged_new_password(self):
        for new in ['123', OLD, '']:
            r = self.change(self.user, new=new)
            self.assertEqual(r.status_code, 400, new)
            self.assertIn('new_password', r.json()['stack'])

    def test_google_only_account_is_pointed_to_reset(self):
        self.user.set_unusable_password()
        self.user.save()
        r = self.change(self.user)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Forgot password', r.json()['message'])

    def test_admin_change_is_audited_without_the_password(self):
        r = self.change(self.admin)
        self.assertEqual(r.status_code, 200, r.content)
        log = AuditLog.objects.get(action=AuditLog.Action.ADMIN_PASSWORD_CHANGED)
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.target_label, 'admin@t.io')
        self.assertEqual(log.details['via'], 'profile')
        self.assertNotIn(NEW, str(log.details))
        self.assertNotIn(OLD, str(log.details))

    def test_failed_admin_attempt_is_not_logged_as_a_change(self):
        self.change(self.admin, current='nope')
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.ADMIN_PASSWORD_CHANGED).exists())

    def test_admin_password_via_profile_update_is_audited(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put('/api/accounts/me/update/', {'password': NEW}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        log = AuditLog.objects.get(action=AuditLog.Action.ADMIN_PASSWORD_CHANGED)
        self.assertEqual(log.details['via'], 'profile_update')
