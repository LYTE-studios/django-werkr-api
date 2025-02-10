from django.test import RequestFactory
import datetime
import tempfile
from unittest.mock import patch

from apps.authentication.models import CustomerProfile, WorkerProfile, AdminProfile
from apps.authentication.utils.authentication_util import AuthenticationUtil
from apps.authentication.utils.jwt_auth_util import JWTAuthUtil
from apps.authentication.views import BaseClientView
from apps.authentication.views import JWTBaseAuthView
from apps.core.assumptions import CMS_GROUP_NAME, CUSTOMERS_GROUP_NAME
from apps.core.assumptions import WORKERS_GROUP_NAME
from apps.core.model_exceptions import DeserializationException
from apps.core.models.settings import Settings
from apps.core.utils.wire_names import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseForbidden
from django.test import RequestFactory
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.authentication.models.dashboard_flow import DashboardFlow
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
from apps.authentication.utils.worker_util import WorkerUtil
from apps.authentication.utils.customer_util import CustomerUtil
from apps.jobs.models import Job, JobState


class BaseClientViewTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BaseClientView.as_view()
        self.client = APIClient()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)

    def test_options_request(self):
        request = self.factory.options("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("allow", response)

    def test_dispatch_with_valid_group(self):
        request = self.factory.get("/")
        request.META["HTTP_CLIENT_SECRET"] = "valid_secret"
        with self.settings(AUTHENTICATION_UTIL=AuthenticationUtil):
            AuthenticationUtil.check_client_secret = lambda req: self.group
            response = self.view(request)
            self.assertEqual(response.status_code, 200)

    def test_dispatch_with_invalid_group(self):
        request = self.factory.get("/")
        request.META["HTTP_CLIENT_SECRET"] = "invalid_secret"
        with self.settings(AUTHENTICATION_UTIL=AuthenticationUtil):
            AuthenticationUtil.check_client_secret = lambda req: None
            response = self.view(request)
            self.assertEqual(response.status_code, 403)


class JWTBaseAuthViewTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = JWTBaseAuthView.as_view()
        self.client = APIClient()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="password123", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.token = AccessToken.for_user(self.user)

    def test_dispatch_with_valid_token(self):
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        request.META["HTTP_CLIENT_SECRET"] = "valid_secret"
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.check_for_authentication = lambda req: self.token
            response = self.view(request)
            self.assertEqual(response.status_code, 200)

    def test_dispatch_with_invalid_token(self):
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        request.META["HTTP_CLIENT_SECRET"] = "valid_secret"
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.check_for_authentication = lambda req: None
            response = self.view(request)
            self.assertEqual(response.status_code, 403)


class JWTAuthenticationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("jwt-authentication")
        self.valid_payload = {"email": "test@example.com", "password": "password123"}
        self.invalid_payload = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }

    def test_post_with_valid_credentials(self):
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.authenticate = lambda email, password, group: {
                "access": "access_token",
                "refresh": "refresh_token",
            }
            response = self.client.post(self.url, self.valid_payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("access", response.data)
            self.assertIn("refresh", response.data)

    def test_post_with_invalid_credentials(self):
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.authenticate = lambda email, password, group: {}
            response = self.client.post(self.url, self.invalid_payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data["message"], "Invalid credentials")


class ProfileMeViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.group = Group.objects.create(name="test_group")
        self.settings = Settings.objects.create(language="en")
        self.user = User.objects.create_user(
            username="testuser",
            password="password123",
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            description="Sample description",
            settings=self.settings,
        )
        self.user.groups.add(self.group)
        self.client.force_authenticate(user=self.user)

    @patch(
        "apps.authentication.utils.profile_util.ProfileUtil.get_user_profile_picture_url",
        return_value="profile_pic_url",
    )
    def test_get_profile(self, mock_get_user_profile_picture_url):
        url = reverse("profile_me")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_id"], str(self.user.id))
        self.assertEqual(response.data["first_name"], "Test")
        self.assertEqual(response.data["last_name"], "User")
        self.assertEqual(response.data["email"], "testuser@example.com")
        self.assertEqual(response.data["description"], "Sample description")
        self.assertEqual(response.data["profile_picture"], "profile_pic_url")
        self.assertEqual(response.data["language"], "en")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key: "new_value",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="new_email@example.com",
    )
    def test_put_profile(self, mock_get_email, mock_get_value):
        url = reverse("profile_me")
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "new_email@example.com",
            "description": "New description",
        }
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertEqual(self.user.email, "new_email@example.com")
        self.assertEqual(self.user.description, "New description")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_put_profile_invalid_data(self, mock_get_value):
        url = reverse("profile_me")
        data = {"first_name": "John"}
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["message"], ("Invalid data",))

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_put_profile_server_error(self, mock_get_value):
        url = reverse("profile_me")
        data = {"first_name": "John"}
        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["message"], ("Server error",))


class LanguageSettingsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.client.login(username="testuser", password="12345")

    @patch("apps.core.models.settings.Settings.objects.all")
    def test_get_languages(self, mock_settings_all):
        mock_settings_all.return_value = [
            Settings(language="en"),
            Settings(language="fr"),
            Settings(language="en"),
        ]
        response = self.client.get(reverse("language_settings"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"languages": ["en", "fr"]})

    @patch("apps.core.utils.formatters.FormattingUtil.get_value", return_value="es")
    @patch("apps.core.models.settings.Settings.objects.create")
    def test_put_language(self, mock_settings_create, mock_get_value):
        settings = Settings(language="en")
        settings.save()
        self.user.settings = settings
        self.user.save()
        mock_settings_create.return_value = settings

        data = {"language": "es"}
        response = self.client.put(
            reverse("language_settings"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.settings.language, "es")
        self.assertEqual(response.json(), {"language": "es"})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_put_language_invalid_data(self, mock_get_value):
        data = {"language": "invalid"}
        response = self.client.put(
            reverse("language_settings"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_put_language_server_error(self, mock_get_value):
        data = {"language": "es"}
        response = self.client.put(
            reverse("language_settings"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"message": ("Server error",)})


class UploadUserProfilePictureViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.client.login(username="testuser", password="12345")

    def test_get_profile_picture(self):
        response = self.client.get(
            reverse("upload_profile_picture", kwargs={"id": self.user.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["profile_picture"])

    def test_put_profile_picture(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
            temp_file.write(b"file_content")
            temp_file.seek(0)
            uploaded_file = SimpleUploadedFile(
                temp_file.name, temp_file.read(), content_type="image/jpeg"
            )
            response = self.client.put(
                reverse("upload_profile_picture", kwargs={"id": self.user.id}),
                {"file": uploaded_file},
                format="multipart",
            )
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.user.refresh_from_db()
            self.assertTrue(self.user.profile_picture.name.endswith(".jpg"))


class PasswordResetRequestViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="test@example.com",
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.send_reset_code"
    )
    def test_post_valid_email(self, mock_send_reset_code, mock_get_email):
        data = {"email": "test@example.com"}
        response = self.client.post(
            reverse("password_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(), {"message": "Password reset email has been sent."}
        )
        mock_send_reset_code.assert_called_once_with(self.user)

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        side_effect=Exception("Invalid email"),
    )
    def test_post_invalid_email(self, mock_get_email):
        data = {"email": "invalid"}
        response = self.client.post(
            reverse("password_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid email",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="notfound@example.com",
    )
    def test_post_email_not_found(self, mock_get_email):
        data = {"email": "notfound@example.com"}
        response = self.client.post(
            reverse("password_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"message": "Email not found."})


class VerifyCodeViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "test@example.com" if key == "email" else "123456"
        ),
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.verify_code",
        return_value=True,
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.create_temporary_token_for_user",
        return_value="temporary_token",
    )
    def test_post_valid_code(self, mock_create_token, mock_verify_code, mock_get_value):
        data = {"email": "test@example.com", "code": "123456"}
        response = self.client.post(
            reverse("password_reset_verify"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"token": "temporary_token"})
        mock_verify_code.assert_called_once_with(self.user, "123456")
        mock_create_token.assert_called_once_with(self.user, "123456")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "test@example.com" if key == "email" else "wrong_code"
        ),
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.verify_code",
        return_value=False,
    )
    def test_post_invalid_code(self, mock_verify_code, mock_get_value):
        data = {"email": "test@example.com", "code": "wrong_code"}
        response = self.client.post(
            reverse("password_reset_verify"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {"message": "Code not verified."})
        mock_verify_code.assert_called_once_with(self.user, "wrong_code")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Invalid data"),
    )
    def test_post_invalid_data(self, mock_get_value):
        data = {"email": "invalid"}
        response = self.client.post(
            reverse("password_reset_verify"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "notfound@example.com" if key == "email" else "123456"
        ),
    )
    def test_post_email_not_found(self, mock_get_value):
        data = {"email": "notfound@example.com", "code": "123456"}
        response = self.client.post(
            reverse("password_reset_verify"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": "Email not found."})


class ResetPasswordViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "valid_token"
            if key == "token"
            else "123456" if key == "code" else "new_password"
        ),
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.get_user_by_token_and_code",
        return_value=User,
    )
    @patch(
        "apps.authentication.utils.encryption_util.EncryptionUtil.encrypt",
        return_value="encrypted_password",
    )
    def test_post_valid_data(self, mock_encrypt, mock_get_user, mock_get_value):
        data = {"token": "valid_token", "code": "123456", "password": "new_password"}
        response = self.client.post(
            reverse("password_reset_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"message": "Password has been reset."})
        mock_get_user.assert_called_once_with("valid_token", "123456")
        mock_encrypt.assert_called_once_with("new_password")
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, "encrypted_password")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "invalid_token"
            if key == "token"
            else "123456" if key == "code" else "new_password"
        ),
    )
    @patch(
        "apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.get_user_by_token_and_code",
        return_value=None,
    )
    def test_post_invalid_token(self, mock_get_user, mock_get_value):
        data = {"token": "invalid_token", "code": "123456", "password": "new_password"}
        response = self.client.post(
            reverse("password_reset_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": "Invalid or expired token"})
        mock_get_user.assert_called_once_with("invalid_token", "123456")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Invalid data"),
    )
    def test_post_invalid_data(self, mock_get_value):
        data = {"token": "invalid"}
        response = self.client.post(
            reverse("password_reset_reset"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid data",)})


class BaseClientViewTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BaseClientView.as_view()
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()

    @patch(
        "apps.authentication.utils.authentication_util.AuthenticationUtil.check_client_secret"
    )
    def test_dispatch_valid_group(self, mock_check_client_secret):
        mock_check_client_secret.return_value = self.group
        request = self.factory.get("/some-url")
        request.user = self.user
        response = self.view(request)
        self.assertNotEqual(response.status_code, HttpResponseForbidden.status_code)

    @patch(
        "apps.authentication.utils.authentication_util.AuthenticationUtil.check_client_secret"
    )
    def test_dispatch_invalid_group(self, mock_check_client_secret):
        mock_check_client_secret.return_value = Group(name="InvalidGroup")
        request = self.factory.get("/some-url")
        request.user = self.user
        response = self.view(request)
        self.assertEqual(response.status_code, HttpResponseForbidden.status_code)

    @patch(
        "apps.authentication.utils.authentication_util.AuthenticationUtil.check_client_secret"
    )
    def test_dispatch_no_group(self, mock_check_client_secret):
        mock_check_client_secret.return_value = None
        request = self.factory.get("/some-url")
        request.user = self.user
        response = self.view(request)
        self.assertEqual(response.status_code, HttpResponseForbidden.status_code)

    def test_options_method(self):
        request = self.factory.options("/some-url")
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["allow"], "GET,POST,UPDATE,DELETE,OPTIONS")


class WorkerRegisterViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=WORKERS_GROUP_NAME)

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: "test_value",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="test@example.com",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_date", return_value="2000-01-01"
    )
    @patch("apps.core.utils.formatters.FormattingUtil.get_address", return_value=None)
    @patch(
        "apps.authentication.utils.encryption_util.EncryptionUtil.encrypt",
        return_value="encrypted_password",
    )
    @patch("apps.authentication.managers.user_manager.UserManager.create_user")
    @patch(
        "apps.authentication.managers.user_manager.UserManager.create_worker_profile"
    )
    def test_post_valid_data(
        self,
        mock_create_worker_profile,
        mock_create_user,
        mock_encrypt,
        mock_get_address,
        mock_get_date,
        mock_get_email,
        mock_get_value,
    ):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "test@example.com",
            "password": "password123",
            "phone_number": "1234567890",
            "date_of_birth": "2000-01-01",
            "iban": "DE89370400440532013000",
            "place_of_birth": "City",
            "ssn": "123-45-6789",
            "worker_address": None,
        }
        response = self.client.post(
            reverse("worker_register"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())
        user = User.objects.get(email="test@example.com")
        self.assertEqual(response.json(), {"id": user.id})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_post_invalid_data(self, mock_get_value):
        data = {"first_name": "John"}
        response = self.client.post(
            reverse("worker_register"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="test@example.com",
    )
    def test_post_user_already_exists(self, mock_get_email):
        User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        data = {"email": "test@example.com"}
        response = self.client.post(
            reverse("worker_register"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.json(), {"message": "User already exists"})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_post_server_error(self, mock_get_value):
        data = {"first_name": "John"}
        response = self.client.post(
            reverse("worker_register"), data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"message": ("Server error",)})


class StatisticsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("statistics_view")
        self.valid_data = {k_worker_id: "worker_id", k_time_frame: k_week}

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "worker_id" if key == k_worker_id else k_week
        ),
    )
    @patch(
        "apps.jobs.services.statistics_service.StatisticsService.get_weekly_stats",
        return_value={"week_stats": "data"},
    )
    def test_post_valid_weekly_data(self, mock_get_weekly_stats, mock_get_value):
        response = self.client.post(
            self.url, self.valid_data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                k_statistics: [
                    {"week_stats": "data"},
                    {"week_stats": "data"},
                    {"week_stats": "data"},
                ]
            },
        )

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "worker_id" if key == k_worker_id else k_month
        ),
    )
    @patch(
        "apps.jobs.services.statistics_service.StatisticsService.get_monthly_stats",
        return_value={"year_stats": "data"},
    )
    def test_post_valid_monthly_data(self, mock_get_monthly_stats, mock_get_value):
        response = self.client.post(
            self.url,
            {k_worker_id: "worker_id", k_time_frame: k_month},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                k_statistics: [
                    {"year_stats": "data"},
                    {"year_stats": "data"},
                    {"year_stats": "data"},
                ]
            },
        )

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_post_invalid_data(self, mock_get_value):
        response = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: (
            "worker_id" if key == k_worker_id else "invalid_time_frame"
        ),
    )
    def test_post_invalid_time_frame(self, mock_get_value):
        response = self.client.post(
            self.url,
            {k_worker_id: "worker_id", k_time_frame: "invalid_time_frame"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: "Invalid time frame"})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_post_server_error(self, mock_get_value):
        response = self.client.post(
            self.url, self.valid_data, content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ("Server error",)})


class WorkerDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("worker_detail", kwargs={"id": self.user.id})

    def test_get_valid_worker(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), WorkerUtil.to_worker_view(self.user))

    def test_get_invalid_worker(self):
        url = reverse("worker_detail", kwargs={"id": 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_valid_worker(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_delete_invalid_worker(self):
        url = reverse("worker_detail", kwargs={"id": 999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key: "new_value",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="new_email@example.com",
    )
    @patch("apps.core.utils.formatters.FormattingUtil.get_address", return_value=None)
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_date", return_value="2000-01-01"
    )
    def test_put_valid_worker(
        self, mock_get_date, mock_get_address, mock_get_email, mock_get_value
    ):
        data = {
            k_first_name: "John",
            k_last_name: "Doe",
            k_phone_number: "1234567890",
            k_email: "new_email@example.com",
            k_address: None,
            k_date_of_birth: "2000-01-01",
            k_billing_address: None,
            k_tax_number: "123456789",
            k_company: "New Company",
        }
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertEqual(self.user.email, "new_email@example.com")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_put_invalid_data(self, mock_get_value):
        data = {k_first_name: "John"}
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_put_server_error(self, mock_get_value):
        data = {k_first_name: "John"}
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ("Server error",)})


class WorkersListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("workers_list")

    @patch(
        "apps.authentication.utils.worker_util.WorkerUtil.to_worker_view",
        side_effect=lambda worker: {"id": worker.id, "email": worker.email},
    )
    def test_get_workers_list(self, mock_to_worker_view):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.worker_util.WorkerUtil.to_worker_view",
        side_effect=lambda worker: {"id": worker.id, "email": worker.email},
    )
    def test_get_workers_list_with_search_term(self, mock_to_worker_view):
        response = self.client.get(self.url, {"search_term": "test"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.worker_util.WorkerUtil.to_worker_view",
        side_effect=lambda worker: {"id": worker.id, "email": worker.email},
    )
    def test_get_workers_list_with_sort_term(self, mock_to_worker_view):
        response = self.client.get(
            self.url, {"sort_term": "email", "algorithm": "descending"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.worker_util.WorkerUtil.to_worker_view",
        side_effect=lambda worker: {"id": worker.id, "email": worker.email},
    )
    def test_get_workers_list_with_pagination(self, mock_to_worker_view):
        response = self.client.get(self.url, {"count": 10, "page": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.worker_util.WorkerUtil.to_worker_view",
        side_effect=lambda worker: {"id": worker.id, "email": worker.email},
    )
    def test_get_workers_list_with_state(self, mock_to_worker_view):
        response = self.client.get(self.url, {"state": "registered"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())


class AcceptWorkerViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("accept_worker", kwargs={"id": self.user.id})

    def test_post_valid_worker(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.worker_profile.accepted)

    def test_post_invalid_worker(self):
        url = reverse("accept_worker", kwargs={"id": 999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CreateCustomerViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=CMS_GROUP_NAME)
        self.url = reverse("create_customer")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key, required=False: "test_value",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="test@example.com",
    )
    @patch("apps.core.utils.formatters.FormattingUtil.get_address", return_value=None)
    @patch(
        "apps.authentication.managers.user_manager.UserManager.create_customer_profile"
    )
    def test_post_valid_data(
        self,
        mock_create_customer_profile,
        mock_get_address,
        mock_get_email,
        mock_get_value,
    ):
        data = {
            k_first_name: "John",
            k_last_name: "Doe",
            k_email: "test@example.com",
            k_address: None,
            k_billing_address: None,
            k_tax_number: "123456789",
            k_company: "Test Company",
            k_phone_number: "1234567890",
        }
        response = self.client.post(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())
        user = User.objects.get(email="test@example.com")
        self.assertEqual(response.json(), {k_customer_id: user.id})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_post_invalid_data(self, mock_get_value):
        data = {k_first_name: "John"}
        response = self.client.post(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="test@example.com",
    )
    def test_post_user_already_exists(self, mock_get_email):
        User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        data = {k_email: "test@example.com"}
        response = self.client.post(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_post_server_error(self, mock_get_value):
        data = {k_first_name: "John"}
        response = self.client.post(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ("Server error",)})


class CustomersListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("customers_list")

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer, has_active_job: {
            "id": customer.id,
            "email": customer.email,
        },
    )
    def test_get_customers_list(self, mock_to_customer_view):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer, has_active_job: {
            "id": customer.id,
            "email": customer.email,
        },
    )
    def test_get_customers_list_with_search_term(self, mock_to_customer_view):
        response = self.client.get(self.url, {"search_term": "test"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer, has_active_job: {
            "id": customer.id,
            "email": customer.email,
        },
    )
    def test_get_customers_list_with_sort_term(self, mock_to_customer_view):
        response = self.client.get(
            self.url, {"sort_term": "email", "algorithm": "descending"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer, has_active_job: {
            "id": customer.id,
            "email": customer.email,
        },
    )
    def test_get_customers_list_with_pagination(self, mock_to_customer_view):
        response = self.client.get(self.url, {"count": 10, "page": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer, has_active_job: {
            "id": customer.id,
            "email": customer.email,
        },
    )
    def test_get_customers_list_with_active_job(self, mock_to_customer_view):
        job = Job.objects.create(
            customer=self.user,
            start_time=datetime.datetime.utcnow(),
            end_time=datetime.datetime.utcnow(),
            job_state=JobState.pending,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())
        job.delete()


class CustomerDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("customer_detail", kwargs={"id": self.user.id})

    def test_get_valid_customer(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), CustomerUtil.to_customer_view(self.user))

    def test_get_invalid_customer(self):
        url = reverse("customer_detail", kwargs={"id": 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_valid_customer(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_delete_invalid_customer(self):
        url = reverse("customer_detail", kwargs={"id": 999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=lambda key: "new_value",
    )
    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_email",
        return_value="new_email@example.com",
    )
    @patch("apps.core.utils.formatters.FormattingUtil.get_address", return_value=None)
    def test_put_valid_customer(self, mock_get_address, mock_get_email, mock_get_value):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "new_email@example.com",
            "phone_number": "1234567890",
            "address": None,
            "billing_address": None,
            "tax_number": "123456789",
            "company": "New Company",
        }
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "John")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertEqual(self.user.email, "new_email@example.com")

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=DeserializationException("Invalid data"),
    )
    def test_put_invalid_data(self, mock_get_value):
        data = {"first_name": "John"}
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"message": ("Invalid data",)})

    @patch(
        "apps.core.utils.formatters.FormattingUtil.get_value",
        side_effect=Exception("Server error"),
    )
    def test_put_server_error(self, mock_get_value):
        data = {"first_name": "John"}
        response = self.client.put(self.url, data, content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {"message": ("Server error",)})


class CustomerSearchTermViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(
            username="testuser", password="12345", email="test@example.com"
        )
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("customer_search_term", kwargs={"search_term": "test"})

    @patch(
        "apps.authentication.utils.customer_util.CustomerUtil.to_customer_view",
        side_effect=lambda customer: {"id": customer.id, "email": customer.email},
    )
    def test_get_customers_with_valid_search_term(self, mock_to_customer_view):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())

    def test_get_customers_with_invalid_search_term(self):
        url = reverse("customer_search_term", kwargs={"search_term": "invalid"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WorkerProfileDetailViewTest(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.worker_profile = WorkerProfile.objects.create(user=self.user)
        self.dashboard_flow = DashboardFlow.objects.create(
            user=self.user,
            car_washing_experience_type="beginner",
            waiter_experience_type="beginner",
            cleaning_experience_type="beginner",
            chauffeur_experience_type="beginner",
            gardening_experience_type="beginner",
            situation_type="flexi",
            work_type="weekday_mornings",
        )
        self.url = reverse("worker-profile-detail", kwargs={"user_id": self.user.id})

    def test_get_worker_profile_detail(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("worker_profile", response.data)
        self.assertIn("dashboard_flow", response.data)
