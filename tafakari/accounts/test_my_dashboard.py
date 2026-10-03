from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from jobs.models import Job

URL = '/api/accounts/me/dashboard/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, **extra)


def make_job(employer, title, **extra):
    return Job.objects.create(employer=employer, title=title, description='d', location_text='Nairobi',
                              job_type='part_time', payment_type='fixed', **extra)


class MyDashboardTests(TestCase):
    def setUp(self):
        self.me = make_user('me@t.io', '0700000001', email_verified=True, is_verified=True)
        self.other = make_user('other@t.io', '0700000002', email_verified=True, is_verified=True)
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def test_worker_and_employer_numbers(self):
        # Jobs I posted: one live, one awaiting approval
        live = make_job(self.me, 'Painter', admin_approved=True, status='active')
        make_job(self.me, 'Plumber')
        # Someone applies to my live job
        JobApplication.objects.create(job=live, worker=self.other, proposed_rate=100, availability_start='2026-10-10')
        # I apply to two of their jobs
        theirs1 = make_job(self.other, 'Driver', admin_approved=True, status='active')
        theirs2 = make_job(self.other, 'Cook', admin_approved=True, status='active')
        JobApplication.objects.create(job=theirs1, worker=self.me, proposed_rate=50, availability_start='2026-10-10')
        JobApplication.objects.create(job=theirs2, worker=self.me, proposed_rate=50, availability_start='2026-10-10',
                                      status='accepted')

        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['applications']['total'], 2)
        self.assertEqual(d['applications']['accepted'], 1)
        self.assertEqual(len(d['recent_applications']), 2)
        self.assertEqual(d['my_jobs']['total'], 2)
        self.assertEqual(d['my_jobs']['pending_approval'], 1)
        self.assertEqual(d['my_jobs']['live'], 1)
        self.assertEqual(d['applicants']['total'], 1)
        painter = next(j for j in d['recent_jobs'] if j['title'] == 'Painter')
        self.assertEqual(painter['applicants'], 1)
        self.assertEqual(d['marketplace']['open_jobs'], 3)

    def test_account_checklist(self):
        d = self.client.get(URL).json()['account']
        self.assertTrue(d['is_approved'])
        self.assertEqual(d['documents_max'], 10)
        done = {c['key']: c['done'] for c in d['checklist']}
        self.assertEqual(done, {'email': True, 'photo': False, 'phone': True, 'documents': False})
        self.assertEqual(d['completion'], 50)

    def test_requires_login(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))
