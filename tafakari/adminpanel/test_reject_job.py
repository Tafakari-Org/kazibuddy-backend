from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog
from jobs.models import Job
from utils.views import build_job_rejected_email


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='Peter Otieno',
                                          phone_number=phone, **extra)


class RejectJobTests(TestCase):
    def setUp(self):
        self.poster = make_user('poster@t.io', '0700000031', email_verified=True, is_verified=True)
        self.admin = make_user('admin@t.io', '0700000032'); self.admin.is_staff = True; self.admin.save()
        self.job = Job.objects.create(employer=self.poster, title='Fix a leaking tap', description='d',
                                      location_text='Nairobi', job_type='temporary', payment_type='fixed',
                                      budget_min=500)
        self.client = APIClient(); self.client.force_authenticate(self.admin)
        self.url = f'/api/adminpanel/jobs/{self.job.id}/reject/'

    @patch('adminpanel.views.send_job_rejected_email')
    def test_reject_flow(self, mail):
        r = self.client.post(self.url, {'reasons': ['missing_details', 'contact_or_payment_info'],
                                        'note': 'Please remove your phone number.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'cancelled')
        self.assertFalse(self.job.admin_approved)
        self.assertEqual(self.job.rejection_reasons, ['missing_details', 'contact_or_payment_info'])

        job_arg, reasons, fixes, note = mail.call_args.args
        self.assertEqual(job_arg.id, self.job.id)
        self.assertIn('Key details are missing (location, dates or budget)', reasons)
        self.assertEqual(len(fixes), 2)
        self.assertEqual(note, 'Please remove your phone number.')
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.JOB_REJECTED).exists())

        # Poster sees readable reasons on their rejected list
        poster = APIClient(); poster.force_authenticate(self.poster)
        data = poster.get(f'/api/jobs/cancelled/{self.poster.id}/').json()
        rows = data['results']['data'] if isinstance(data.get('results'), dict) else data['results']
        self.assertEqual(rows[0]['rejection_reasons'][0], 'Key details are missing (location, dates or budget)')
        self.assertEqual(rows[0]['rejection_note'], 'Please remove your phone number.')

    @patch('adminpanel.views.send_job_approved_email')
    @patch('adminpanel.views.send_job_rejected_email')
    def test_approving_later_clears_rejection(self, _rej, _ok):
        self.client.post(self.url, {'reasons': ['unclear_description']}, format='json')
        self.client.post(f'/api/adminpanel/jobs/{self.job.id}/approve/')
        self.job.refresh_from_db()
        self.assertTrue(self.job.admin_approved)
        self.assertIsNone(self.job.rejected_at)
        self.assertEqual(self.job.rejection_reasons, [])

    @patch('adminpanel.views.send_job_rejected_email')
    def test_validation_and_permissions(self, _mail):
        self.assertEqual(self.client.post(self.url, {'reasons': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url, {'reasons': ['nope']}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url, {'reasons': ['other']}, format='json').status_code, 400)
        poster = APIClient(); poster.force_authenticate(self.poster)
        self.assertEqual(poster.post(self.url, {'reasons': ['duplicate']}, format='json').status_code, 403)

    def test_status_endpoint_requires_owner_or_admin(self):
        stranger = make_user('x@t.io', '0700000033')
        c = APIClient(); c.force_authenticate(stranger)
        r = c.post(f'/api/jobs/{self.job.id}/status/', {'status': 'cancelled'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.job.refresh_from_db()
        self.assertNotEqual(self.job.status, 'cancelled')

    def test_email_renders(self):
        subject, html = build_job_rejected_email(self.job, ['The job description is unclear or too short'],
                                                 ['Explain the tasks step by step.'], 'Add <b>more</b> detail.')
        self.assertIn('Fix a leaking tap', subject)
        self.assertIn('Your job wasn&rsquo;t approved yet', html)
        self.assertIn('The job description is unclear or too short', html)
        self.assertIn('Explain the tasks step by step.', html)
        self.assertIn('Add &lt;b&gt;more&lt;/b&gt; detail.', html)
        self.assertIn('KES 500', html)
