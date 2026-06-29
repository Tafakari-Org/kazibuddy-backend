from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from workers.models import WorkerProfile
import uuid
# Create your tests here.
User = CustomUser

class WorkerProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="worker"
        )
        self.employer_user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="employer"
        )

    def test_create_worker_profile_success(self):
        profile = WorkerProfile.objects.create(
            user=self.user,
            location="Nairobi",
            years_experience=5,
            hourly_rate=100
        )
        self.assertEqual(profile.location, "Nairobi")
        self.assertEqual(profile.user.user_type, "worker")

    def test_create_worker_profile_invalid_user_type(self):
        profile = WorkerProfile(
            user=self.employer_user,
            location="Nairobi"
        )
        with self.assertRaises(ValidationError):
            profile.save()

class WorkerProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="worker"
        )
        self.employer_user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="employer"
        )
        
        self.existing_worker_user = User.objects.create_user(
            email="existing@example.com",
            phone_number="+254700000002",
            password="Testpassword123!",
            user_type="worker"
        )
        self.worker_profile = WorkerProfile.objects.create(
            user=self.existing_worker_user,
            location="Nairobi",
            years_experience=5,
            hourly_rate=100
        )

    def test_create_worker_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-worker-profile')
        data = {
            "location": "Nairobi",
            "years_experience": 5,
            "hourly_rate": 100
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WorkerProfile.objects.count(), 2)
        
    
    def test_create_worker_profile_upgrade_employer(self):
        self.client.force_authenticate(user=self.employer_user)
        url = reverse('create-worker-profile')
        data = {
            "location": "Nairobi",
            "years_experience": 5,
            "hourly_rate": 100
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.employer_user.refresh_from_db()
        self.assertEqual(self.employer_user.user_type, "both")

    def test_create_worker_profile_duplicate(self):
        self.client.force_authenticate(user=self.existing_worker_user)
        url = reverse('create-worker-profile')
        data = {
            "location": "Nairobi",
            "years_experience": 5,
            "hourly_rate": 100
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_worker_profile(self):
        url = reverse('view-worker-profile', kwargs={'id': self.worker_profile.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['location'], "Nairobi")

    def test_retrieve_worker_profile_not_found(self):
        url = reverse('view-worker-profile', kwargs={'id': self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_worker_profile(self):
        self.client.force_authenticate(user=self.existing_worker_user)
        url = reverse('update-worker-profile', kwargs={'id': self.worker_profile.id})
        data = {
            "location": "Mombasa",
            "years_experience": 10,
            "hourly_rate": 200
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.worker_profile.refresh_from_db()
        self.assertEqual(self.worker_profile.location, "Mombasa")

    def test_update_worker_profile_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('update-worker-profile', kwargs={'id': self.worker_profile.id})
        data = {
            "location": "Mombasa",
            "years_experience": 10,
            "hourly_rate": 200
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_worker_profiles(self):
        url = reverse('list-worker-profiles')
        response = self.client.get(url)
        print("LIST WORKER PROFILES => ", response.data["count"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_total_workers(self):
        url = reverse('total-workers')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], 1)
