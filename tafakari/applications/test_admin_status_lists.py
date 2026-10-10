from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from applications.models import JobApplication
from jobs.models import Job


def make_user(email, phone, name, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=name,
                                          phone_number=phone, email_verified=True, is_verified=True, **extra)


def make_job(employer, title):
    return Job.objects.create(employer=employer, title=title, description='d', location_text='Nairobi',
                              job_type='part_time', payment_type='daily', admin_approved=True)


class AdminStatusListFilterTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', 'Admin', is_staff=True)
        employer = make_user('boss@t.io', '0700000002', 'Boss')
        self.cleaning = make_job(employer, 'Office cleaning')
        self.driving = make_job(employer, 'Delivery driver')
        workers = [make_user(f'w{i}@t.io', f'07100000{i:02d}', name)
                   for i, name in enumerate(['Amina Otieno', 'Brian Kamau', 'Carol Wanjiru', 'David Amin'])]
        for w in workers:
            JobApplication.objects.create(job=self.cleaning, worker=w, proposed_rate=500,
                                          availability_start=date(2026, 11, 1))
        JobApplication.objects.create(job=self.driving, worker=workers[0], proposed_rate=800,
                                      availability_start=date(2026, 11, 1))
        JobApplication.objects.create(job=self.cleaning, worker=make_user('r@t.io', '0700000099', 'Rejected Ruth'),
                                      proposed_rate=500, availability_start=date(2026, 11, 1), status='rejected')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def names(self, r):
        return sorted(a['worker']['full_name'] for a in r.json()['results']['data'])

    def test_unfiltered_list_is_unchanged(self):
        r = self.client.get('/api/applications/pending/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['count'], 5)

    def test_filter_by_job(self):
        r = self.client.get('/api/applications/pending/', {'job': str(self.cleaning.id)})
        self.assertEqual(r.json()['count'], 4)
        self.assertEqual({a['job']['id'] for a in r.json()['results']['data']}, {str(self.cleaning.id)})

    def test_status_is_respected_with_job_filter(self):
        r = self.client.get('/api/applications/rejected/', {'job': str(self.cleaning.id)})
        self.assertEqual(self.names(r), ['Rejected Ruth'])

    def test_search_by_name_or_email(self):
        r = self.client.get('/api/applications/pending/', {'job': str(self.cleaning.id), 'search': 'amin'})
        self.assertEqual(self.names(r), ['Amina Otieno', 'David Amin'])
        r = self.client.get('/api/applications/pending/', {'job': str(self.cleaning.id), 'search': 'w2@t.io'})
        self.assertEqual(self.names(r), ['Carol Wanjiru'])

    def test_pagination_metadata_with_filters(self):
        r = self.client.get('/api/applications/pending/', {'job': str(self.cleaning.id), 'page_size': 3, 'page': 2})
        d = r.json()
        self.assertEqual((d['count'], d['total_pages'], d['page']), (4, 2, 2))
        self.assertEqual(len(d['results']['data']), 1)

    def test_bad_job_id(self):
        self.assertEqual(self.client.get('/api/applications/accepted/', {'job': 'nope'}).status_code, 400)

    def test_admin_only(self):
        self.client.force_authenticate(make_user('x@t.io', '0700000098', 'X'))
        self.assertEqual(self.client.get('/api/applications/pending/').status_code, 403)
