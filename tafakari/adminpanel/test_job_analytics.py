from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from jobs.models import Job, JobCategory

URL = '/api/adminpanel/jobs/analytics/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, **extra)


def make_job(employer, **extra):
    fields = dict(title='Job', description='d', location_text='Nairobi', job_type='temporary', payment_type='fixed')
    fields.update(extra)
    return Job.objects.create(employer=employer, **fields)


class JobAnalyticsTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', email_verified=True, is_verified=True)
        self.admin.is_staff = True
        self.admin.user_type = 'admin'
        self.admin.save()
        worker = make_user('worker@t.io', '0700000002', email_verified=True, is_verified=True)
        plumbing = JobCategory.objects.create(name='Plumbing')

        live = make_job(self.admin, status='active', admin_approved=True, category=plumbing,
                        urgency_level='urgent', budget_max=1000, views_count=7)
        make_job(self.admin, status='draft', budget_min=500, location_text='Mombasa')   # pending approval
        make_job(self.admin, status='cancelled', rejected_at=timezone.now())            # rejected
        JobApplication.objects.create(job=live, worker=worker, proposed_rate=900, availability_start=timezone.localdate())

        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_counts_and_shape(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['totals']['total'], 3)
        self.assertEqual(d['totals']['active'], 1)
        self.assertEqual(d['totals']['views'], 7)
        self.assertEqual(d['totals']['applications'], 1)
        self.assertEqual(d['approval'], {'approved': 1, 'pending': 1, 'rejected': 1})

        status = {row['key']: row['count'] for row in d['status']}
        self.assertEqual(status, {'draft': 1, 'active': 1, 'paused': 0, 'filled': 0, 'cancelled': 1, 'completed': 0})
        self.assertEqual(next(u['count'] for u in d['urgency'] if u['key'] == 'urgent'), 1)

        # budget_max where set, otherwise budget_min
        self.assertEqual(d['budget'], {'total': 1500.0, 'average': 750.0, 'jobs_with_budget': 2})
        self.assertEqual(d['categories'], [{'id': d['categories'][0]['id'], 'name': 'Plumbing', 'count': 1}])
        self.assertEqual(d['uncategorized'], 2)
        self.assertEqual(d['locations'][0], {'name': 'Nairobi', 'count': 2})
        self.assertEqual(d['top_jobs'][0]['applications'], 1)
        self.assertEqual(len(d['trend']), 30)
        self.assertEqual(sum(day['count'] for day in d['trend']), 3)

    def test_non_admin_forbidden(self):
        member = CustomUser.objects.get(email='worker@t.io')
        client = APIClient(); client.force_authenticate(member)
        self.assertEqual(client.get(URL).status_code, 403)
