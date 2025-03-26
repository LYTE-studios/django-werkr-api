import uuid
import jwt
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.jobs.models.application import JobApplication
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.jobs.models.job import Job
from apps.core.models.geo import Address
from apps.jobs.models.job_application_state import JobApplicationState
from unittest.mock import patch, MagicMock
from apps.core.utils.wire_names import *

User = get_user_model()


class DownloadContractViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create test user
        self.user = User.objects.create(
            email="test@test.com",
            username="testuser",
            first_name="Test",
            last_name="Worker"
        )
        self.address = Address.objects.create()
        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
            worker_type=WorkerProfile.WorkerType.STUDENT
        )
        self.job = Job.objects.create(
            customer=self.user,
            address=self.address
        )
        with patch('apps.jobs.services.contract_service.JobApplicationService.fetch_directions') as mock_fetch:
            mock_fetch.return_value = {
                'from_lat': 50.8503,
                'from_lng': 4.3517,
                'to_lat': 50.8503,
                'to_lng': 4.3517,
                'directions': {}
            }
            mock_fetch.return_value.save = MagicMock()
            self.job_application = JobApplication.objects.create(
                id=uuid.uuid4(),
                job=self.job,
                worker=self.user,
                address=self.address,
                application_state=JobApplicationState.approved,
                created_at='2023-01-01T00:00:00Z',
                modified_at='2023-01-01T00:00:00Z'
            )
        self.url = reverse('download_contract', kwargs={k_id: self.job_application.id})

    @patch('apps.legal.utils.contract_util.ContractUtil.generate_contract')
    def test_download_contract_success(self, mock_generate_contract):
        mock_generate_contract.return_value = 'contract.pdf'
        with open('contract.pdf', 'wb') as f:
            f.write(b'Test PDF content')

        # Create JWT token for authentication
        token = jwt.encode(
            {'user_id': str(self.user.id)},
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename=', response['Content-Disposition'])

    def test_download_contract_not_approved(self):
        self.job_application.application_state = JobApplicationState.pending
        self.job_application.save()

        # Create JWT token for authentication
        token = jwt.encode(
            {'user_id': str(self.user.id)},
            settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), 'Worker not approved')
