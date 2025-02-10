from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.legal.services.dimona_service import DimonaService, fetch_dimona
from django.contrib.auth import get_user_model
import json
from datetime import datetime
import asyncio

User = get_user_model()


class DimonaServiceTest(TestCase):

    @patch("apps.legal.services.dimona_service.requests.post")
    @patch("apps.legal.services.dimona_service.jwt.encode")
    def test_get_auth_token(self, mock_jwt_encode, mock_requests_post):
        mock_jwt_encode.return_value = "mock_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"access_token": "mock_access_token"})
        mock_requests_post.return_value = mock_response

        token = DimonaService._get_auth_token()
        self.assertEqual(token, "mock_access_token")

    @patch("apps.legal.services.dimona_service.requests.post")
    def test_make_post(self, mock_requests_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        with patch.object(DimonaService, "_get_auth_token", return_value="mock_token"):
            response = DimonaService._make_post("mock_url", {"key": "value"})
            self.assertEqual(response.status_code, 200)

    @patch("apps.legal.services.dimona_service.requests.get")
    def test_make_get(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        with patch.object(DimonaService, "_get_auth_token", return_value="mock_token"):
            response = DimonaService._make_get("mock_url")
            self.assertEqual(response.status_code, 200)

    def test_format_ssn(self):
        ssn = "123-45-6789"
        formatted_ssn = DimonaService.format_ssn(ssn)
        self.assertEqual(formatted_ssn, "0123456789")

    @patch("apps.legal.services.dimona_service.WorkerProfile.objects.filter")
    @patch("apps.legal.services.dimona_service.DimonaService._make_post")
    def test_fetch_employee_data(self, mock_make_post, mock_worker_profile_filter):
        mock_worker_profile = MagicMock()
        mock_worker_profile.ssn = "123-45-6789"
        mock_worker_profile_filter.return_value.first.return_value = mock_worker_profile
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"items": [{"worker": "mock_worker_data"}]}
        mock_make_post.return_value = mock_response

        user = MagicMock()
        employee_data = DimonaService.fetch_employee_data(user)
        self.assertEqual(employee_data, "mock_worker_data")

    @patch("apps.legal.services.dimona_service.Dimona.objects.filter")
    @patch("apps.legal.services.dimona_service.DimonaService._make_post")
    def test_cancel_dimona(self, mock_make_post, mock_dimona_filter):
        mock_dimona = MagicMock()
        mock_dimona_filter.return_value.first.return_value = mock_dimona

        application = MagicMock()
        DimonaService.cancel_dimona(application)
        mock_make_post.assert_called_once()
        mock_dimona.delete.assert_called_once()

    @patch("apps.legal.services.dimona_service.Dimona.objects.filter")
    @patch("apps.legal.services.dimona_service.DimonaService._make_post")
    def test_update_dimona(self, mock_make_post, mock_dimona_filter):
        mock_dimona = MagicMock()
        mock_dimona_filter.return_value.first.return_value = mock_dimona

        application = MagicMock()
        registration = MagicMock()
        registration.start_time = datetime.datetime.now()
        registration.end_time = datetime.datetime.now() + datetime.timedelta(hours=1)

        DimonaService.update_dimona(application, registration)
        mock_make_post.assert_called_once()

    def test_get_type_for_user(self):
        user = MagicMock()
        user.worker_profile.worker_type = WorkerProfile.WorkerType.STUDENT
        self.assertEqual(DimonaService.get_type_for_user(user), "STU")

    @patch("apps.legal.services.dimona_service.DimonaService.get_type_for_user")
    @patch("apps.legal.services.dimona_service.Dimona.objects.filter")
    @patch("apps.legal.services.dimona_service.DimonaService._make_post")
    def test_create_dimona(
        self, mock_make_post, mock_dimona_filter, mock_get_type_for_user
    ):
        mock_get_type_for_user.return_value = "STU"
        mock_dimona_filter.return_value.exists.return_value = False
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"Location": "mock_location/123"}
        mock_make_post.return_value = mock_response

        application = MagicMock()
        user = MagicMock()
        user.worker_profile.ssn = "123-45-6789"
        application.worker = user

        with patch(
            "apps.legal.services.dimona_service.FormattingUtil.to_user_timezone",
            return_value=datetime.datetime.now(),
        ):
            DimonaService.create_dimona(application)
            mock_make_post.assert_called_once()

    @patch("apps.legal.services.dimona_service.Dimona.objects.get")
    @patch("apps.legal.services.dimona_service.DimonaService._make_get")
    @patch("apps.legal.services.dimona_service.NotificationManager.notify_admin")
    def test_fetch_dimona(self, mock_notify_admin, mock_make_get, mock_dimona_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"declarationStatus": {"result": "A"}}
        mock_make_get.return_value = mock_response
        mock_dimona = MagicMock()
        mock_dimona_get.return_value = mock_dimona

        asyncio.run(fetch_dimona("mock_id"))
        mock_dimona.save.assert_called_once()
