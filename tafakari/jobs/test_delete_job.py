import os
import shutil
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CustomUser
from assignments.models import Assignment, AssignmentCheckin
from jobs.models import Job, JobAttachment, JobImage


def make_user(email, phone):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='Peter Otieno',
                                          phone_number=phone, email_verified=True, is_verified=True)


@patch('jobs.views.send_otp_to_email')
class PosterDeleteJobFilesTests(TestCase):
    """A poster deleting their own job removes its files from disk, including check-in photos."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

        self.poster = make_user('poster@t.io', '0700000071')
        worker = make_user('worker@t.io', '0700000072')
        self.job = Job.objects.create(employer=self.poster, title='Fix a leaking tap', description='d',
                                      location_text='Nairobi', job_type='temporary', payment_type='fixed')
        assignment = Assignment.objects.create(job=self.job, worker=worker, employer=self.poster)

        self.files = {}
        url = self._file('cover.jpg', 'image'); JobImage.objects.create(job=self.job, image_url=url, file_name='cover.jpg')
        url = self._file('quote.pdf', 'attachment'); JobAttachment.objects.create(job=self.job, file_url=url, file_name='quote.pdf')
        url = self._file('start.jpg', 'checkin'); AssignmentCheckin.objects.create(
            assignment=assignment, worker=worker, checkin_type='start', photo_url=url)
        AssignmentCheckin.objects.create(assignment=assignment, worker=worker, checkin_type='end')  # no photo

        self.client = APIClient(); self.client.force_authenticate(self.poster)

    def _file(self, name, label):
        folder = os.path.join(self.media, 'images'); os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, 'w') as f:
            f.write('x')
        self.files[label] = path
        return f"{settings.MEDIA_URL.rstrip('/')}/images/{name}"

    def test_files_removed_from_disk(self, _mail):
        r = self.client.delete(f'/api/jobs/{self.job.id}/delete/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(Job.objects.filter(id=self.job.id).exists())
        for label, path in self.files.items():
            self.assertFalse(os.path.exists(path), f"{label} file was left on disk")
        self.assertFalse(AssignmentCheckin.objects.exists())
