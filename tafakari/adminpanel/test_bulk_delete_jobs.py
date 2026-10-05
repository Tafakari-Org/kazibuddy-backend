import os
import shutil
import tempfile
import uuid
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from assignments.models import Assignment, AssignmentCheckin
from auditlogs.models import AuditLog
from jobs.models import Job, JobAttachment, JobImage
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


class BulkDeleteJobFilesTests(TestCase):
    """Deleting a job removes its files from disk, including assignment check-in photos."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

        poster = make_user('poster@t.io', '0700000051', email_verified=True, is_verified=True)
        worker = make_user('worker@t.io', '0700000052', email_verified=True, is_verified=True)
        self.admin = make_user('admin@t.io', '0700000053'); self.admin.is_staff = True; self.admin.save()
        self.job = make_job(poster, 'Fix a leaking tap')
        assignment = Assignment.objects.create(job=self.job, worker=worker, employer=poster)

        self.files = {}
        url = self._file('cover.jpg', 'image'); JobImage.objects.create(job=self.job, image_url=url, file_name='cover.jpg')
        url = self._file('quote.pdf', 'attachment'); JobAttachment.objects.create(job=self.job, file_url=url, file_name='quote.pdf')
        url = self._file('start.jpg', 'checkin'); AssignmentCheckin.objects.create(
            assignment=assignment, worker=worker, checkin_type='start', photo_url=url)
        AssignmentCheckin.objects.create(assignment=assignment, worker=worker, checkin_type='end')  # no photo

        self.client = APIClient(); self.client.force_authenticate(self.admin)

    def _file(self, name, label):
        folder = os.path.join(self.media, 'images'); os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, 'w') as f:
            f.write('x')
        self.files[label] = path
        return f"{settings.MEDIA_URL.rstrip('/')}/images/{name}"

    @patch('adminpanel.job_deletion.send_job_deleted_email')
    def test_files_removed_from_disk(self, _mail):
        r = self.client.post(URL, {'job_ids': [str(self.job.id)], 'reasons': ['expired']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()['deleted']), 1)
        for label, path in self.files.items():
            self.assertFalse(os.path.exists(path), f"{label} file was left on disk")
        self.assertFalse(AssignmentCheckin.objects.exists())
