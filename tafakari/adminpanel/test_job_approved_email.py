from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from jobs.models import Job, JobCategory
from utils.views import build_job_approved_email


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='Peter Otieno',
                                          phone_number=phone, **extra)


class JobApprovedEmailTests(TestCase):
    def setUp(self):
        self.poster = make_user('poster@t.io', '0700000021', email_verified=True, is_verified=True)
        cat = JobCategory.objects.create(name='Cleaning & Housekeeping')
        self.job = Job.objects.create(
            employer=self.poster, category=cat, title='Deep clean a 3-bedroom house', description='d',
            location_text='Kilimani, Nairobi', job_type='temporary', payment_type='fixed',
            budget_min=2500, budget_max=4000, urgency_level='high',
            start_date=date(2026, 10, 10), end_date=date(2026, 10, 11), max_applicants=5,
        )

    def test_approving_job_sends_email(self):
        admin = make_user('admin@t.io', '0700000022'); admin.is_staff = True; admin.save()
        client = APIClient(); client.force_authenticate(admin)
        with patch('adminpanel.views.send_job_approved_email') as mail:
            r = client.post(f'/api/adminpanel/jobs/{self.job.id}/approve/')
        self.assertEqual(r.status_code, 200)
        mail.assert_called_once()
        self.assertEqual(mail.call_args.args[0].id, self.job.id)

    def test_email_renders_job_summary(self):
        subject, html = build_job_approved_email(self.job)
        self.assertIn('Deep clean a 3-bedroom house', subject)
        self.assertIn('Your job is live, Peter!', html)
        self.assertIn('KES 2,500 – 4,000 · Fixed', html)
        self.assertIn('Kilimani, Nairobi', html)
        self.assertIn('Cleaning &amp; Housekeeping', html)
        self.assertIn('10 Oct 2026 → 11 Oct 2026', html)
        self.assertIn('Up to 5', html)
        self.assertIn('/dashboard?tab=my-jobs', html)
