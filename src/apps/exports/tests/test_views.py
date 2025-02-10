from apps.exports.jobs.monthly_exports import create_monthly_exports
import datetime
from django.urls import reverse
from django.test import TestCase, Client
from rest_framework import status
from rest_framework.test import APIClient
from apps.exports.models import ExportFile
from apps.core.models.geo import Address
from apps.core.utils.formatters import FormattingUtil
from apps.exports.managers.export_manager import ExportManager
from unittest.mock import patch


class ExportsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("exports-list")
        self.export_file = ExportFile.objects.create(
            name="Test Export", created=datetime.datetime.now()
        )

    def test_get_exports(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("exports", response.data)
        self.assertEqual(len(response.data["exports"]), 1)

    @patch.object(ExportManager, "create_time_registations_export")
    @patch.object(ExportManager, "create_active_werkers_export")
    def test_post_exports(
        self, mock_create_time_registations_export, mock_create_active_werkers_export
    ):
        data = {"start_time": "2023-01-01", "end_time": "2023-01-31"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_create_time_registations_export.assert_called_once()
        mock_create_active_werkers_export.assert_called_once()

    def test_post_exports_invalid_data(self):
        data = {"start_time": "invalid-date", "end_time": "invalid-date"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
