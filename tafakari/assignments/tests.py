from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from employers.models import EmployerProfile
from workers.models import WorkerProfile
from jobs.models import JobCategory, Job
from applications.models import JobApplication
from assignments.models import Assignment, AssignmentCheckin, AssignmentMilestone
from unittest.mock import patch

User = get_user_model()

class AssignmentModelTests(TestCase):
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

    def test_create_assignment(self):
        assignment = Assignment.objects.create(
            job=self.job,
            worker=self.worker_profile,
            employer=self.employer_profile
        )
        self.assertEqual(assignment.job, self.job)
        self.assertEqual(assignment.worker, self.worker_profile)
        self.assertEqual(Assignment.objects.count(), 1)


class AssignmentAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            phone_number="+254700000000",
            password="Testpassword123!"
        )

        self.employer_user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="employer",
            full_name="John Employer"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.employer_user,
            business_type="individual"
        )

        self.worker_user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000002",
            password="Testpassword123!",
            user_type="worker",
            full_name="Jane Worker"
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

        self.application = JobApplication.objects.create(
            job=self.job,
            worker=self.worker_profile,
            proposed_rate=500.00,
            availability_start="2026-07-01",
            status="pending"
        )

        self.assignment = Assignment.objects.create(
            job=self.job,
            worker=self.worker_profile,
            employer=self.employer_profile
        )

    def test_list_assignments(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('list-create-assignment')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('data', response.data['results'])

    @patch('assignments.views.notify_rejected_applicants.delay')
    def test_create_assignment(self, mock_notify):
        new_job = Job.objects.create(
            employer=self.employer_profile,
            category=self.category,
            title="Another Job",
            description="Another desc.",
            location_text="Remote",
            job_type=Job.JobType.PART_TIME,
            payment_type=Job.PaymentType.FIXED,
            admin_approved=True,
            status=Job.Status.ACTIVE
        )
        JobApplication.objects.create(
            job=new_job,
            worker=self.worker_profile,
            proposed_rate=500.00,
            availability_start="2026-07-01",
            status="pending"
        )

        self.client.force_authenticate(user=self.admin_user)
        url = reverse('list-create-assignment')
        data = {
            "job": new_job.id,
            "worker": self.worker_profile.id,
            "employer": self.employer_profile.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Assignment.objects.count(), 2)

    def test_retrieve_assignment(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('assignment-detail', kwargs={'assignment_id': self.assignment.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['id'], str(self.assignment.id))

    def test_list_worker_assignments(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('list-worker-assignments', kwargs={'worker_id': self.worker_profile.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_checkin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('list-create-checkins', kwargs={'assignment_id': self.assignment.id})
        data = {
            "worker": self.worker_profile.id,
            "checkin_type": "start",
            "location": "Nairobi"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_milestone(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('list-create-milestones', kwargs={'assignment_id': self.assignment.id})
        data = {
            "title": "First Draft",
            "description": "Deliver the first draft",
            "status": "pending"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_milestone_status(self):
        milestone = AssignmentMilestone.objects.create(
            assignment=self.assignment,
            title="First Draft",
            status="pending"
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('update-milestone-status', kwargs={'milestone_id': milestone.id})
        data = {
            "status": "completed",
            "completion_notes": "All done"
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, "completed")
