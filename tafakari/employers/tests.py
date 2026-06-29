from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from employers.models import EmployerProfile
import uuid

User = CustomUser

class EmployerProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer"
        )
        self.worker_user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="worker"
        )

    def test_create_employer_profile_success(self):
        profile = EmployerProfile.objects.create(
            user=self.user,
            business_type="individual",
            company_name="Test Company"
        )
        self.assertEqual(profile.company_name, "Test Company")
        self.assertEqual(profile.user.user_type, "employer")

    def test_create_employer_profile_invalid_user_type(self):
        profile = EmployerProfile(
            user=self.worker_user,
            business_type="individual"
        )
        with self.assertRaises(ValidationError):
            profile.save()


class EmployerProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employer@example.com",
            phone_number="+254700000000",
            password="Testpassword123!",
            user_type="employer"
        )
        self.worker_user = User.objects.create_user(
            email="worker@example.com",
            phone_number="+254700000001",
            password="Testpassword123!",
            user_type="worker"
        )
        
        self.existing_employer_user = User.objects.create_user(
            email="existing@example.com",
            phone_number="+254700000002",
            password="Testpassword123!",
            user_type="employer"
        )
        self.employer_profile = EmployerProfile.objects.create(
            user=self.existing_employer_user,
            business_type="small_business",
            company_name="Existing Company"
        )

    def test_create_employer_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('create-employer-profile')
        data = {
            "business_type": "individual",
            "company_name": "New Company",
            "industry": "Tech"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EmployerProfile.objects.count(), 2)

    def test_create_employer_profile_upgrade_worker(self):
        self.client.force_authenticate(user=self.worker_user)
        url = reverse('create-employer-profile')
        data = {
            "business_type": "individual",
            "company_name": "Worker Company"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.worker_user.refresh_from_db()
        self.assertEqual(self.worker_user.user_type, "both")

    def test_create_employer_profile_duplicate(self):
        self.client.force_authenticate(user=self.existing_employer_user)
        url = reverse('create-employer-profile')
        data = {
            "business_type": "individual"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_employer_profile(self):
        url = reverse('retrieve-employer-profile', kwargs={'id': self.existing_employer_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['company_name'], "Existing Company")

    def test_retrieve_employer_profile_not_found(self):
        url = reverse('retrieve-employer-profile', kwargs={'id': self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_employer_profile(self):
        self.client.force_authenticate(user=self.existing_employer_user)
        url = reverse('update-employer-profile', kwargs={'id': self.employer_profile.id})
        data = {
            "company_name": "Updated Company"
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employer_profile.refresh_from_db()
        self.assertEqual(self.employer_profile.company_name, "Updated Company")

    def test_update_employer_profile_forbidden(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('update-employer-profile', kwargs={'id': self.employer_profile.id})
        data = {
            "company_name": "Hacked Company"
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_total_employers(self):
        url = reverse('total-employers')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], 1)
