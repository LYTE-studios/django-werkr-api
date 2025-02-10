import uuid
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from apps.jobs.models.application import JobApplication
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.jobs.models.job import Job
from apps.core.models.geo import Address
from apps.jobs.models.job_application_state import JobApplicationState
from unittest.mock import patch
from apps.core.utils.wire_names import *


class DownloadContractViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.worker_profile = WorkerProfile.objects.create(user_id=uuid.uuid4())
        self.address = Address.objects.create()
        self.job = Job.objects.create(customer_id=uuid.uuid4())
        self.job_application = JobApplication.objects.create(
            id=uuid.uuid4(),
            job=self.job,
            worker=self.worker_profile,
            address=self.address,
            application_state=JobApplicationState.approved,
            created_at="2023-01-01T00:00:00Z",
            modified_at="2023-01-01T00:00:00Z",
        )
        self.url = reverse("download_contract", kwargs={k_id: self.job_application.id})

    @patch("apps.legal.views.generate_contract")
    def test_download_contract_success(self, mock_generate_contract):
        mock_generate_contract.return_value = "contract.pdf"
        with open("contract.pdf", "wb") as f:
            f.write(b"Test PDF content")

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

    def test_download_contract_not_approved(self):
        self.job_application.application_state = JobApplicationState.pending
        self.job_application.save()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "Worker not approved")
