import uuid

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from .models import AuditLog

URL = '/api/adminpanel/audit-logs/bulk-delete/'


def make_user(email, phone, user_type):
    user = CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='A B', phone_number=phone)
    user.is_staff = True
    user.user_type = user_type
    user.save()
    return user


def make_log(age, action=AuditLog.Action.JOB_APPROVED):
    log = AuditLog.objects.create(action=action, target_type=AuditLog.TargetType.JOB, target_label='Job')
    AuditLog.objects.filter(pk=log.pk).update(created_at=timezone.now() - age)
    return log


class AuditLogBulkDeleteTests(TestCase):
    def setUp(self):
        self.superadmin = make_user('super@t.io', '0700000061', 'super_admin')
        self.admin = make_user('admin@t.io', '0700000062', 'admin')
        self.client = APIClient(); self.client.force_authenticate(self.superadmin)

    def test_deletes_only_entries_older_than_two_months(self):
        old = make_log(relativedelta(months=2, days=1))
        older = make_log(relativedelta(months=6), AuditLog.Action.USER_REJECTED)
        recent = make_log(relativedelta(months=2) - relativedelta(days=1))
        missing = str(uuid.uuid4())

        r = self.client.post(URL, {'ids': [str(old.id), str(older.id), str(recent.id), missing]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d['deleted'], 2)
        self.assertEqual({s['id']: s['reason'] for s in d['skipped']},
                         {str(recent.id): 'Less than 2 months old', missing: 'Entry not found'})

        self.assertFalse(AuditLog.objects.filter(id__in=[old.id, older.id]).exists())
        self.assertTrue(AuditLog.objects.filter(id=recent.id).exists())

        trace = AuditLog.objects.get(action=AuditLog.Action.AUDIT_LOGS_DELETED)
        self.assertEqual(trace.actor, self.superadmin)
        self.assertEqual(trace.details['count'], 2)
        self.assertEqual(trace.details['actions'], {'job.approved': 1, 'user.rejected': 1})

    def test_records_of_deletions_are_never_deleted(self):
        trace = make_log(relativedelta(years=1), AuditLog.Action.AUDIT_LOGS_DELETED)
        r = self.client.post(URL, {'ids': [str(trace.id)]}, format='json')
        self.assertEqual(r.json()['deleted'], 0)
        self.assertTrue(AuditLog.objects.filter(id=trace.id).exists())
        self.assertEqual(AuditLog.objects.count(), 1)  # nothing deleted, so no new trace

    def test_regular_admin_forbidden(self):
        old = make_log(relativedelta(months=3))
        client = APIClient(); client.force_authenticate(self.admin)
        self.assertEqual(client.post(URL, {'ids': [str(old.id)]}, format='json').status_code, 403)
        self.assertTrue(AuditLog.objects.filter(id=old.id).exists())

    def test_filters_report_deletion_rules(self):
        d = self.client.get('/api/adminpanel/audit-logs/filters/').json()['deletion']
        self.assertTrue(d['allowed'])
        self.assertEqual(d['min_age_months'], 2)
        client = APIClient(); client.force_authenticate(self.admin)
        self.assertFalse(client.get('/api/adminpanel/audit-logs/filters/').json()['deletion']['allowed'])

    def test_validation(self):
        self.assertEqual(self.client.post(URL, {'ids': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {'ids': ['x'] * 501}, format='json').status_code, 400)
