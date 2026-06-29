from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from employers.models import EmployerProfile
from workers.models import WorkerProfile
from jobs.models import JobCategory, Job
from applications.models import JobApplication

User = get_user_model()

class JobApplicationModelTests(TestCase):
    def setUp(self):
        self.employer_user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.employer_user,
            business_type="individual"
        )

        self.worker_user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="worker"
        )
        self.worker_profile = WorkerProfile.objects.create(
            user=self.worker_user
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

    def test_create_job_application(self):
        application = JobApplication.objects.create(
            job=self.job,
            worker=self.worker_profile,
            cover_letter="I am very interested.",
            proposed_rate=500.00,
            availability_start="2026-07-01",
            status="pending"
        )
        self.assertEqual(application.status, "pending")
        self.assertEqual(application.proposed_rate, 500.00)

class JobApplicationAPITests(APITestCase):
    def setUp(self):
        # Users
        self.employer_user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer",
            full_name="John Doe"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.employer_user,
            business_type="individual"
        )

        self.worker_user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="worker",
            full_name="Jane Doe"
        )
        self.worker_profile = WorkerProfile.objects.create(
            user=self.worker_user
        )

        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            phone_number="+254700000002",
            password="Testpassword123!"
        )

        # Job stuff
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
        
        # Existing application
        self.application = JobApplication.objects.create(
            job=self.job,
            worker=self.worker_profile,
            cover_letter="My existing application.",
            proposed_rate=1000.00,
            availability_start="2026-08-01",
            status="pending"
        )

    def test_create_job_application(self):
        # Create a new job to apply to
        new_job = Job.objects.create(
            employer=self.employer_profile,
            category=self.category,
            title="Another Job",
            description="Need a minimalist logo.",
            location_text="Remote",
            job_type=Job.JobType.PART_TIME,
            payment_type=Job.PaymentType.FIXED,
            admin_approved=True,
            status=Job.Status.ACTIVE
        )
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('create-job-application', kwargs={'job_id': new_job.id})
        data = {
            "proposed_rate": "500.00",
            "availability_start": "2026-07-01",
            "cover_letter": "Hire me!"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(JobApplication.objects.count(), 2)

    def test_create_duplicate_application(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('create-job-application', kwargs={'job_id': self.job.id})
        data = {
            "proposed_rate": "500.00",
            "availability_start": "2026-07-01"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_job_applications(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('my-job-applications')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('applications', response.data)

    def test_job_application_detail_retrieve(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('job-application-detail', kwargs={'application_id': self.application.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_job_application_update(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('job-application-detail', kwargs={'application_id': self.application.id})
        data = {
            "proposed_rate": "1200.00"
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.proposed_rate, 1200.00)

    def test_job_application_delete(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('job-application-detail', kwargs={'application_id': self.application.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(JobApplication.objects.count(), 0)

    def test_all_job_applications_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('all-job-applications')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_all_job_applications_forbidden(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('all-job-applications')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
