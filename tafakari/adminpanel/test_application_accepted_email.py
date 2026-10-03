from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from jobs.models import Job
from utils.views import build_application_accepted_email


def make_user(email, phone, name='Grace Akinyi', **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=name,
                                          phone_number=phone, **extra)


class ApplicationAcceptedEmailTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000041', name='Admin'); self.admin.is_staff = True; self.admin.save()
        self.poster = make_user('poster@t.io', '0700000042', name='Peter Otieno')
        self.worker = make_user('worker@t.io', '0700000043')
        self.job = Job.objects.create(employer=self.poster, title='Paint a 2-room apartment', description='d',
                                      location_text='Ruaka', job_type='temporary', payment_type='fixed',
                                      budget_min=6000, budget_max=9000, admin_approved=True, status='active',
                                      start_date=date(2026, 10, 12))
        self.app = JobApplication.objects.create(job=self.job, worker=self.worker, proposed_rate=7500,
                                                 availability_start=date(2026, 10, 13))
        self.client = APIClient(); self.client.force_authenticate(self.admin)

    @patch('adminpanel.views.send_otp_to_email')
    @patch('adminpanel.views.send_application_accepted_email')
    def test_status_change_to_accepted_sends_congrats(self, congrats, generic):
        r = self.client.patch(f'/api/adminpanel/applications/{self.app.id}/status/', {'status': 'accepted'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        congrats.assert_called_once()
        worker, job, application = congrats.call_args.args
        self.assertEqual((worker.id, job.id, application.id), (self.worker.id, self.job.id, self.app.id))
        generic.assert_not_called()

    @patch('adminpanel.views.send_otp_to_email')
    @patch('adminpanel.views.send_application_accepted_email')
    def test_other_statuses_keep_generic_notice(self, congrats, generic):
        self.client.patch(f'/api/adminpanel/applications/{self.app.id}/status/', {'status': 'shortlisted'}, format='json')
        congrats.assert_not_called()
        generic.assert_called_once()

    @patch('assignments.views.notify_rejected_applicants')
    @patch('assignments.views.send_otp_to_email')
    @patch('assignments.views.send_application_accepted_email')
    def test_assigning_worker_sends_congrats(self, congrats, generic, _notify):
        r = self.client.post('/api/assignments/', {'job': str(self.job.id), 'worker': str(self.worker.id),
                                                   'employer': str(self.poster.id)}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        worker, job, application = congrats.call_args.args
        self.assertEqual(worker.id, self.worker.id)
        self.assertEqual(application.id, self.app.id)
        # The poster still gets their assignment email; the worker no longer gets the generic one.
        recipients = [c.kwargs['user'].id for c in generic.call_args_list]
        self.assertEqual(recipients, [self.poster.id])

    def test_email_renders_with_proposed_rate(self):
        subject, html = build_application_accepted_email(self.worker, self.job, self.app)
        self.assertIn('You got the job: Paint a 2-room apartment', subject)
        self.assertIn('Congratulations, Grace', html)
        self.assertIn('KES 7,500 · Fixed', html)            # their proposed rate, not the job minimum
        self.assertIn('Tuesday, 13 October 2026', html)     # their availability date
        self.assertIn('Peter Otieno', html)
        self.assertIn('/dashboard?tab=my-applications', html)
