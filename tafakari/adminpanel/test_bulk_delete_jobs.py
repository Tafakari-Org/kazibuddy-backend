import uuid
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from auditlogs.models import AuditLog
from jobs.models import Job
from utils.views import build_job_deleted_email

URL = '/api/adminpanel/jobs/bulk-delete/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='Peter Otieno',
                                          phone_number=phone, **extra)


def make_job(employer, title):
    return Job.objects.create(employer=employer, title=title, description='d', location_text='Nairobi',
                              job_type='temporary', payment_type='fixed', budget_min=500)


class BulkDeleteJobsTests(TestCase):
    def setUp(self):
        self.poster = make_user('poster@t.io', '0700000041', email_verified=True, is_verified=True)
        self.worker = make_user('worker@t.io', '0700000042', email_verified=True, is_verified=True)
        self.admin = make_user('admin@t.io', '0700000043'); self.admin.is_staff = True; self.admin.save()
        self.a = make_job(self.poster, 'Fix a leaking tap')
        self.b = make_job(self.poster, 'Paint a fence')
        JobApplication.objects.create(job=self.a, worker=self.worker, proposed_rate=500, status='accepted',
                                      availability_start=timezone.localdate())
        self.client = APIClient(); self.client.force_authenticate(self.admin)

    @patch('adminpanel.job_deletion.send_job_deleted_email')
    def test_bulk_delete_emails_poster_and_logs(self, mail):
        missing = str(uuid.uuid4())
        r = self.client.post(URL, {'job_ids': [str(self.a.id), str(self.b.id), missing],
                                   'reasons': ['duplicate', 'other'], 'note': 'Posted twice.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual({j['title'] for j in d['deleted']}, {'Fix a leaking tap', 'Paint a fence'})
        self.assertEqual(d['skipped'], [{'id': missing, 'title': None, 'reason': 'Job not found'}])

        self.assertFalse(Job.objects.filter(id__in=[self.a.id, self.b.id]).exists())
        self.assertFalse(JobApplication.objects.exists())  # cascaded

        self.assertEqual(mail.call_count, 2)
        email, subject, html = mail.call_args_list[0].args
        self.assertEqual(email, 'poster@t.io')
        self.assertIn('was removed from KaziBuddy', subject)
        self.assertIn('This duplicates another job you posted', html)
        self.assertIn('Posted twice.', html)

        logs = AuditLog.objects.filter(action=AuditLog.Action.JOB_DELETED)
        self.assertEqual(logs.count(), 2)
        log = logs.get(target_label='Fix a leaking tap')
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.details['applications'], 1)
        self.assertEqual(log.details['note'], 'Posted twice.')
        self.assertIn('This duplicates another job you posted', log.details['reasons'])

    def test_validation(self):
        ids = [str(self.a.id)]
        self.assertEqual(self.client.post(URL, {'job_ids': ids, 'reasons': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {'job_ids': ids, 'reasons': ['bogus']}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {'job_ids': ids, 'reasons': ['other']}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL, {'job_ids': [], 'reasons': ['expired']}, format='json').status_code, 400)
        self.assertTrue(Job.objects.filter(id=self.a.id).exists())

    def test_non_admin_forbidden(self):
        client = APIClient(); client.force_authenticate(self.poster)
        r = client.post(URL, {'job_ids': [str(self.a.id)], 'reasons': ['expired']}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Job.objects.filter(id=self.a.id).exists())

    def test_reasons_endpoint(self):
        r = self.client.get('/api/adminpanel/jobs/deletion-reasons/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('duplicate', [x['value'] for x in r.json()['reasons']])

    def test_email_renders(self):
        subject, html = build_job_deleted_email(self.a, ['The listing is out of date and no longer active'], '')
        self.assertIn('Fix a leaking tap', subject)
        self.assertIn('Why it was removed', html)
