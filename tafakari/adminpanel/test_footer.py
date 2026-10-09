from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from auditlogs.models import AuditLog
from jobs.models import Job, JobCategory

from .models import FooterCategory, FooterSettings, FooterSocialLink

URL = '/api/adminpanel/footer/'


def make_user(email, phone, **extra):
    return CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name=email.split('@')[0],
                                          phone_number=phone, **extra)


class FooterTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@t.io', '0700000001', email_verified=True, is_verified=True)
        self.admin.is_staff = True
        self.admin.user_type = 'admin'
        self.admin.save()
        self.worker = make_user('worker@t.io', '0700000002', email_verified=True, is_verified=True)
        self.cleaners = JobCategory.objects.create(name='Cleaners')
        self.drivers = JobCategory.objects.create(name='Drivers')
        self.client = APIClient()

    def body(self, **overrides):
        data = {
            "contact": {"phone": "+254 711 222 333", "email": "help@kazibuddy.co.ke", "location": "Mombasa"},
            "social_links": [
                {"platform": "facebook", "url": "https://facebook.com/kazibuddy"},
                {"platform": "x", "url": "https://x.com/kazibuddy"},
            ],
            "categories": [
                {"category_id": str(self.drivers.id), "icon": "car"},
                {"category_id": str(self.cleaners.id), "icon": "home"},
            ],
        }
        data.update(overrides)
        return data

    def test_public_get_needs_no_auth(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {'contact', 'social_links', 'categories', 'updated_at'})

    def test_non_admin_cannot_update(self):
        self.assertIn(self.client.put(URL, self.body(), format='json').status_code, (401, 403))
        self.client.force_authenticate(self.worker)
        self.assertEqual(self.client.put(URL, self.body(), format='json').status_code, 403)

    def test_admin_update_replaces_everything_in_order(self):
        FooterSocialLink.objects.create(platform='youtube', url='https://youtube.com/old')
        self.client.force_authenticate(self.admin)
        r = self.client.put(URL, self.body(), format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d['contact']['phone'], '+254 711 222 333')
        self.assertEqual([s['platform'] for s in d['social_links']], ['facebook', 'x'])
        self.assertEqual([c['name'] for c in d['categories']], ['Drivers', 'Cleaners'])
        self.assertEqual(d['categories'][0]['icon'], 'car')
        self.assertEqual(FooterSettings.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.FOOTER_UPDATED).exists())

    def test_job_count_only_counts_open_approved_jobs(self):
        def job(**extra):
            return Job.objects.create(title='Job', description='d', category=self.cleaners, employer=self.worker,
                                      location_text='Nairobi', job_type='part_time', payment_type='daily', **extra)
        job(admin_approved=True)
        job(admin_approved=True)
        job(admin_approved=False)
        job(admin_approved=True, is_assigned=True)
        job(admin_approved=True, status=Job.Status.CANCELLED)
        FooterCategory.objects.create(category=self.cleaners)
        FooterCategory.objects.create(category=self.drivers)
        counts = {c['name']: c['job_count'] for c in self.client.get(URL).json()['categories']}
        self.assertEqual(counts, {'Cleaners': 2, 'Drivers': 0})

    def test_rejects_bad_input(self):
        self.client.force_authenticate(self.admin)
        bad = [
            self.body(social_links=[{"platform": "myspace", "url": "https://myspace.com"}]),
            self.body(social_links=[{"platform": "facebook", "url": "not a url"}]),
            self.body(contact={"email": "nope"}),
            self.body(categories=[{"category_id": str(self.drivers.id)}, {"category_id": str(self.drivers.id)}]),
            self.body(categories=[{"category_id": "00000000-0000-0000-0000-000000000000"}]),
        ]
        for data in bad:
            self.assertEqual(self.client.put(URL, data, format='json').status_code, 400, data)

    def test_errors_are_flattened_per_field(self):
        self.client.force_authenticate(self.admin)
        links = [{"platform": "facebook", "url": "https://facebook.com/k"}, {"platform": "x", "url": "nope"}]
        r = self.client.put(URL, self.body(social_links=links), format='json')
        self.assertEqual(list(r.json()['stack']), ['social_links.1.url'])

    def test_inactive_categories_are_hidden(self):
        self.cleaners.is_active = False
        self.cleaners.save()
        FooterCategory.objects.create(category=self.cleaners)
        self.assertEqual(self.client.get(URL).json()['categories'], [])
