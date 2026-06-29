from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from employers.models import EmployerProfile
from jobs.models import JobCategory, Job
import uuid

User = get_user_model()

class JobModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.user,
            business_type="individual"
        )
        self.category = JobCategory.objects.create(
            name="Software Development",
            description="Coding and stuff"
        )

    def test_create_job(self):
        job = Job.objects.create(
            employer=self.employer_profile,
            category=self.category,
            title="Senior Python Developer",
            description="Looking for an experienced Python dev.",
            location_text="Nairobi, Kenya",
            job_type=Job.JobType.FULL_TIME,
            payment_type=Job.PaymentType.FIXED
        )
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.status, Job.Status.DRAFT)
        
    def test_search_vector_updated_on_save(self):
        job = Job.objects.create(
            employer=self.employer_profile,
            category=self.category,
            title="React Developer",
            description="Need someone good at React.",
            location_text="Remote",
            job_type=Job.JobType.CONTRACT,
            payment_type=Job.PaymentType.HOURLY
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.search_vector)


class JobAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.user,
            business_type="individual"
        )
        self.category = JobCategory.objects.create(
            name="Design",
            description="Graphic Design"
        )
        self.job = Job.objects.create(
            employer=self.employer_profile,
            category=self.category,
            title="Logo Designer",
            description="Need a minimalist logo.",
            location_text="Remote",
            job_type=Job.JobType.PART_TIME,
            payment_type=Job.PaymentType.FIXED,
            admin_approved=True,
            status=Job.Status.ACTIVE
        )

    def test_list_jobs(self):
        url = reverse('job-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_job(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-job')
        data = {
            "category": self.category.id,
            "title": "UX Researcher",
            "description": "Research user behaviors.",
            "location_text": "Nairobi",
            "job_type": "contract",
            "payment_type": "fixed",
            "budget_min": 1000.00,
            "budget_max": 2000.00,
            "max_applicants": 5
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Job.objects.count(), 2)

    def test_create_job_unauthenticated(self):
        url = reverse('create-job')
        data = {
            "title": "UX Researcher",
            "description": "Research user behaviors.",
            "location_text": "Nairobi",
            "job_type": "contract",
            "payment_type": "fixed"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_job(self):
        url = reverse('job-detail', kwargs={'job_id': self.job.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['title'], "Logo Designer")
