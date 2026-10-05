from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from jobs.models import Job, JobSkill
from skills.models import Skill


def make_user(email, phone, staff=False):
    user = CustomUser.objects.create_user(email=email, password='Passw0rd!x', full_name='A B', phone_number=phone,
                                          email_verified=True, is_verified=True)
    if staff:
        user.is_staff = True
        user.user_type = 'admin'
        user.save()
    return user


class JobDetailTests(TestCase):
    def setUp(self):
        self.poster = make_user('poster@t.io', '0700000091')
        self.other = make_user('other@t.io', '0700000092')
        self.admin = make_user('admin@t.io', '0700000093', staff=True)
        self.job = Job.objects.create(employer=self.poster, title='Fix a tap', description='d', location_text='Nairobi',
                                      job_type='temporary', payment_type='fixed', status='cancelled',
                                      rejected_at=timezone.now(), rejection_reasons=['duplicate'],
                                      rejection_note='Posted twice')
        JobSkill.objects.create(job=self.job, skill=Skill.objects.create(name='Plumbing'))
        self.url = f'/api/jobs/{self.job.id}/'

    def get(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        r = client.get(self.url)
        self.assertEqual(r.status_code, 200)
        return r.json()['data']

    def test_skills_include_names(self):
        self.assertEqual(self.get()['job_skills'][0]['skill_name'], 'Plumbing')

    def test_rejection_details_only_for_admin_and_poster(self):
        for user in (self.admin, self.poster):
            d = self.get(user)
            self.assertEqual(d['rejection_reasons'], ['This duplicates another job you posted'])
            self.assertEqual(d['rejection_note'], 'Posted twice')
        for user in (self.other, None):
            self.assertNotIn('rejection_note', self.get(user))
