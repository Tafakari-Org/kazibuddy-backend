from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from unittest.mock import patch, MagicMock
import uuid

from .models import CustomUser, OTPVerification


# Helpers
def make_user(
    email="test@example.com",
    phone_number="+254700000000",
    password="StrongPass123!",
    full_name="Test User",
    user_type="worker",
    email_verified=True,
    is_verified=True,
    is_active=True,
):
    """Factory for creating a CustomUser for tests."""
    user = CustomUser.objects.create_user(
        email=email,
        phone_number=phone_number,
        password=password,
        full_name=full_name,
        user_type=user_type,
    )
    user.email_verified = email_verified
    user.is_verified = is_verified
    user.is_active = is_active
    user.save()
    return user


# Model Tests
class CustomUserManagerTests(TestCase):
    """Tests for CustomUserManager."""

    def test_create_user_with_email(self):
        user = CustomUser.objects.create_user(
            email="user@example.com",
            password="Pass123!",
            full_name="Email User",
            user_type="worker",
        )
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("Pass123!"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_user_with_phone(self):
        user = CustomUser.objects.create_user(
            phone_number="+254711111111",
            password="Pass123!",
            full_name="Phone User",
            user_type="employer",
        )
        self.assertEqual(user.phone_number, "+254711111111")
        self.assertTrue(user.check_password("Pass123!"))

    def test_create_user_without_email_or_phone_raises(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(password="Pass123!", full_name="No ID", user_type="worker")

    def test_create_user_without_password_sets_unusable(self):
        user = CustomUser.objects.create_user(
            email="nopw@example.com",
            full_name="No Password",
            user_type="worker",
        )
        self.assertFalse(user.has_usable_password())

    def test_create_superuser_requires_phone(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_superuser(password="Admin123!")

    def test_create_superuser_requires_password(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_superuser(phone_number="+254799999999")

    def test_create_superuser_sets_staff_and_superuser(self):
        user = CustomUser.objects.create_superuser(
            phone_number="+254788888888",
            email="admin@example.com",
            password="Admin123!",
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_email_is_normalised(self):
        user = CustomUser.objects.create_user(
            email="User@EXAMPLE.COM",
            password="Pass123!",
            full_name="Norm User",
            user_type="worker",
        )
        self.assertEqual(user.email, "User@example.com")


class CustomUserModelTests(TestCase):
    """Tests for CustomUser model fields and __str__."""

    def test_str_representation(self):
        user = make_user(email="jane@example.com", full_name="Jane Doe")
        self.assertEqual(str(user), "Jane Doe (jane@example.com)")

    def test_uuid_primary_key(self):
        user = make_user()
        self.assertIsInstance(user.id, uuid.UUID)

    def test_defaults(self):
        user = make_user()
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_oauth_user)
        self.assertIsNone(user.deleted_at)

    def test_user_types_choices(self):
        valid_types = [c[0] for c in CustomUser.USER_TYPES]
        self.assertIn("worker", valid_types)
        self.assertIn("employer", valid_types)
        self.assertIn("admin", valid_types)


class OTPVerificationModelTests(TestCase):
    """Tests for OTPVerification model."""

    def setUp(self):
        self.user = make_user()

    def test_create_otp(self):
        otp = OTPVerification.objects.create(
            user=self.user,
            otp_code="123456",
            otp_type="registration",
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )
        self.assertEqual(otp.otp_code, "123456")
        self.assertEqual(otp.attempts, 0)

    def test_str_representation(self):
        otp = OTPVerification.objects.create(
            user=self.user,
            otp_code="654321",
            otp_type="login",
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )
        self.assertIn(self.user.email, str(otp))
        self.assertIn("login", str(otp))


# API Endpoint Tests
class RegisterViewTests(APITestCase):
    """Tests for POST /accounts/register/"""

    url = reverse("register")

    VALID_PAYLOAD = {
        "email": "newuser@example.com",
        "phone_number": "+254700000001",
        "password": "StrongPass123!",
        "full_name": "New User",
        "user_type": "worker",
    }

    @patch("accounts.views.cleanup_unverified_user.apply_async")
    @patch("accounts.views.send_otp_to_email")
    @patch("accounts.views.generate_otp", return_value="123456")
    def test_successful_registration(self, mock_otp, mock_email, mock_task):
        response = self.client.post(self.url, self.VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("user_id", response.data)
        self.assertTrue(CustomUser.objects.filter(email="newuser@example.com").exists())

    @patch("accounts.views.cleanup_unverified_user.apply_async")
    @patch("accounts.views.send_otp_to_email")
    @patch("accounts.views.generate_otp", return_value="123456")
    def test_duplicate_email_returns_400(self, mock_otp, mock_email, mock_task):
        make_user(email="newuser@example.com", phone_number="+254700000099")
        response = self.client.post(self.url, self.VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_missing_required_fields_returns_400(self):
        response = self.client.post(self.url, {"email": "x@x.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.cleanup_unverified_user.apply_async")
    @patch("accounts.views.send_otp_to_email", side_effect=Exception("SMTP down"))
    @patch("accounts.views.generate_otp", return_value="123456")
    def test_otp_send_failure_rolls_back_user(self, mock_otp, mock_email, mock_task):
        response = self.client.post(self.url, self.VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        # User must NOT persist when OTP delivery fails
        self.assertFalse(CustomUser.objects.filter(email="newuser@example.com").exists())


class LoginViewTests(APITestCase):
    """Tests for POST /accounts/login/"""

    url = "/api/accounts/login/"

    def setUp(self):
        self.user = make_user(
            email="login@example.com",
            phone_number="+254700000002",
            password="LoginPass123!",
            email_verified=True,
            is_verified=True,
        )

    def _post(self, identifier, password):
        return self.client.post(
            self.url,
            {"identifier": identifier, "password": password},
            format="json",
        )

    def test_login_with_email_succeeds(self):
        response = self._post("login@example.com", "LoginPass123!")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_login_with_phone_succeeds(self):
        response = self._post("+254700000002", "LoginPass123!")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)

    def test_wrong_password_returns_401(self):
        response = self._post("login@example.com", "WrongPassword!")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_user_returns_401(self):
        response = self._post("ghost@example.com", "AnyPass123!")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_email_returns_403(self):
        self.user.email_verified = False
        self.user.save()
        response = self._post("login@example.com", "LoginPass123!")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Email not verified", response.data["error"])

    def test_unapproved_user_returns_403(self):
        self.user.email_verified = True
        self.user.is_verified = False
        self.user.save()
        response = self._post("login@example.com", "LoginPass123!")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("admin", response.data["error"])

    def test_inactive_user_returns_401(self):
        self.user.is_active = False
        self.user.save()
        response = self._post("login@example.com", "LoginPass123!")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileViewTests(APITestCase):
    """Tests for GET /accounts/me/"""

    url = reverse("profile")

    def setUp(self):
        self.user = make_user(email="profile@example.com")
        self.client.force_authenticate(user=self.user)

    def test_authenticated_user_gets_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "profile@example.com")
        self.assertIn("user_type", response.data)
        self.assertIn("full_name", response.data)

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UpdateUserProfileViewTests(APITestCase):
    """Tests for PUT /accounts/me/update/"""

    url = reverse("update_profile")

    def setUp(self):
        self.user = make_user(email="update@example.com", full_name="Old Name")
        self.client.force_authenticate(user=self.user)

    def test_update_full_name(self):
        response = self.client.put(self.url, {"full_name": "New Name"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "New Name")

    def test_update_phone_number(self):
        response = self.client.put(
            self.url, {"phone_number": "+254700000099"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, "+254700000099")

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.put(self.url, {"full_name": "Hacker"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutViewTests(APITestCase):
    """Tests for POST /accounts/logout/"""

    url = reverse("logout")

    def setUp(self):
        self.user = make_user(email="logout@example.com")
        self.client.force_authenticate(user=self.user)

    def test_logout_authenticated_user(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Logout successful", response.data["message"])

    def test_logout_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DeleteAccountViewTests(APITestCase):
    """Tests for DELETE /accounts/me/delete/"""

    url = reverse("delete_profile")

    def setUp(self):
        self.user = make_user(email="delete@example.com")
        self.client.force_authenticate(user=self.user)

    def test_authenticated_user_can_delete_account(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(CustomUser.objects.filter(email="delete@example.com").exists())

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class VerifyEmailViewTests(APITestCase):
    """Tests for POST /accounts/verify-email/"""

    url = reverse("verify_email")

    def setUp(self):
        self.user = make_user(email="verify@example.com", email_verified=False)

    @patch("accounts.views.validate_otp", return_value=True)
    def test_valid_otp_verifies_email(self, mock_validate):
        response = self.client.post(
            self.url,
            {
                "user_id": str(self.user.id),
                "otp_code": "123456",
                "otp_type": "registration",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    @patch("accounts.views.validate_otp", return_value=False)
    def test_invalid_otp_returns_400(self, mock_validate):
        response = self.client.post(
            self.url,
            {
                "user_id": str(self.user.id),
                "otp_code": "000000",
                "otp_type": "registration",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_user_returns_404(self):
        response = self.client.post(
            self.url,
            {
                "user_id": str(uuid.uuid4()),
                "otp_code": "123456",
                "otp_type": "registration",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PasswordResetRequestViewTests(APITestCase):
    """Tests for POST /accounts/password-reset-request/"""

    url = reverse("password_reset_request")

    def setUp(self):
        self.user = make_user(email="reset@example.com")

    @patch("accounts.views.send_password_reset_email")
    def test_existing_email_sends_reset_link(self, mock_send):
        response = self.client.post(self.url, {"email": "reset@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_called_once()

    @patch("accounts.views.send_password_reset_email")
    def test_nonexistent_email_still_returns_200(self, mock_send):
        """Prevents email enumeration — always returns 200."""
        response = self.client.post(
            self.url, {"email": "ghost@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send.assert_not_called()

    def test_invalid_email_format_returns_error(self):
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)


class PasswordResetConfirmViewTests(APITestCase):
    """Tests for POST /accounts/password-reset-confirm/"""

    url = reverse("password_reset_confirm")

    def setUp(self):
        self.user = make_user(email="confirm@example.com", password="OldPass123!")
        generator = PasswordResetTokenGenerator()
        self.token = generator.make_token(self.user)
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))

    def test_valid_token_resets_password(self):
        response = self.client.post(
            self.url,
            {
                "uidb64": self.uidb64,
                "token": self.token,
                "new_password": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass123!"))

    def test_invalid_token_returns_error(self):
        response = self.client.post(
            self.url,
            {
                "uidb64": self.uidb64,
                "token": "invalid-token",
                "new_password": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_uid_returns_error(self):
        response = self.client.post(
            self.url,
            {
                "uidb64": "invaliduid",
                "token": self.token,
                "new_password": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)

    def test_weak_password_returns_error(self):
        response = self.client.post(
            self.url,
            {
                "uidb64": self.uidb64,
                "token": self.token,
                "new_password": "123",
            },
            format="json",
        )
        self.assertNotEqual(response.status_code, status.HTTP_200_OK)
