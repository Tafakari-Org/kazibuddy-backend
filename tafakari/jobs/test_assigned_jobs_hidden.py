from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from jobs.models import Job, JobCategory


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, email_verified=True, is_verified=True, **extra)


class AssignedJobsHiddenTests(TestCase):
    def setUp(self):
        self.poster = make_user('poster@t.io', '0700000001')
        self.worker = make_user('worker@t.io', '0700000002')
        self.stranger = make_user('stranger@t.io', '0700000003')
        self.admin = make_user('admin@t.io', '0700000004', is_staff=True)
        self.cat = JobCategory.objects.create(name='Cleaning')

        def job(title, **extra):
            return Job.objects.create(employer=self.poster, category=self.cat, title=title, description='d',
                                      location_text='Nairobi', job_type='part_time', payment_type='daily', **extra)
        self.open = job('Open job', admin_approved=True)
        self.assigned = job('Assigned job', admin_approved=True, is_assigned=True)
        self.unapproved = job('Unapproved job')
        JobApplication.objects.create(job=self.assigned, worker=self.worker, proposed_rate=500,
                                      availability_start=date(2026, 11, 1), status='accepted')
        self.client = APIClient()

    def titles(self, r):
        body = r.json()
        return sorted(j['title'] for j in body.get('data', body.get('results', [])))

    def test_category_list_hides_assigned_and_unapproved(self):
        r = self.client.get(f'/api/jobs/categories/{self.cat.id}/jobs/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.titles(r), ['Open job'])

    def test_assigned_job_detail_hidden_from_public_and_strangers(self):
        url = f'/api/jobs/{self.assigned.id}/'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['code'], 'job_filled')
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_assigned_job_detail_visible_to_poster_admin_and_applicant(self):
        url = f'/api/jobs/{self.assigned.id}/'
        for user in (self.poster, self.admin, self.worker):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).status_code, 200, user.email)

    def test_open_job_detail_still_public(self):
        self.assertEqual(self.client.get(f'/api/jobs/{self.open.id}/').status_code, 200)

    def test_cannot_apply_to_assigned_job(self):
        self.client.force_authenticate(self.stranger)
        r = self.client.post(f'/api/applications/{self.assigned.id}/apply/', {
            'proposed_rate': 500, 'availability_start': '2026-11-01', 'cover_letter': 'hi'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('already been assigned', r.json()['message'])
