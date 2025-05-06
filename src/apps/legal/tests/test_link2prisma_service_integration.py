"""
Integration tests for Link2Prisma service.

These tests make actual API calls to the Link2Prisma test environment.
To run these tests specifically:

    pytest src/apps/legal/tests/test_link2prisma_service_integration.py -v

Note: These tests require proper test environment credentials in your .env file:
- LINK2PRISMA_BASE_URL: Test environment URL
- LINK2PRISMA_PFX_PATH: Path to test certificate
- LINK2PRISMA_PFX_PASSWORD: Test certificate password
- LINK2PRISMA_EMPLOYER_REF: Test employer reference
"""

import pytest
from django.test import TransactionTestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from apps.legal.services.link2prisma_service import Link2PrismaService
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.jobs.models.job import Job
from apps.jobs.models.application import JobApplication
from apps.jobs.models.job_application_state import JobApplicationState

User = get_user_model()

@pytest.mark.integration
class TestLink2PrismaServiceIntegration(TransactionTestCase):
    def setUp(self):
        """Set up test data"""
        # Create test address
        self.address = Address.objects.create(
            street_name="Test Street",
            house_number="123",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8503,  # Brussels coordinates
            longitude=4.3517
        )

        # Create test worker
        self.worker = User.objects.create_user(
            username="testworker",
            email="test.worker@example.com",
            password="testpass123",
            first_name="Test",
            last_name="Worker",
            date_joined=timezone.now()
        )

        # Create worker profile
        self.worker_profile = WorkerProfile.objects.create(
            user=self.worker,
            ssn="12345678901",  # Test SSN
            date_of_birth=datetime(1990, 1, 1),
            place_of_birth="Brussels",
            iban="BE68539007547034",
            worker_address=self.address,
            worker_type="student",
            hours=20
        )

        # Create job address
        self.job_address = Address.objects.create(
            street_name="Job Street",
            house_number="456",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8467,  # Different location in Brussels
            longitude=4.3517
        )

        # Create test customer
        self.customer = User.objects.create_user(
            username="testcustomer",
            email="test.customer@example.com",
            password="testpass123",
            first_name="Test",
            last_name="Customer"
        )

        # Create test job
        self.job = Job.objects.create(
            title="Test Job",
            description="Test job description",
            customer=self.customer,
            address=self.job_address,
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=4),
            application_start_time=datetime.now(),
            application_end_time=datetime.now() + timedelta(days=1),
            max_workers=1,
            selected_workers=0
        )

        # Create application address
        self.application_address = Address.objects.create(
            street_name="Application Street",
            house_number="789",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8431,  # Another location in Brussels
            longitude=4.3517
        )

        # Create job application
        self.job_application = JobApplication.objects.create(
            job=self.job,
            worker=self.worker,
            address=self.application_address,
            application_state=JobApplicationState.pending,
            created_at=timezone.now(),
            modified_at=timezone.now()
        )

    def test_health_check(self):
        """Test the health check endpoint"""
        try:
            result = Link2PrismaService.test_connection()
            self.assertTrue(result)
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

    def test_worker_sync_flow(self):
        """Test the complete worker sync flow"""
        # Check if Link2Prisma is properly configured
        try:
            Link2PrismaService.test_connection()
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

        # First check if worker exists
        worker_exists_response = Link2PrismaService._make_request(
            method='GET',
            endpoint=f'workerExists/{self.worker_profile.ssn}'
        )
        self.assertIsNotNone(worker_exists_response)

        # Sync worker (this will create or update the worker)
        Link2PrismaService.sync_worker(self.worker)

        # Verify worker exists after sync
        worker_exists_response = Link2PrismaService._make_request(
            method='GET',
            endpoint=f'workerExists/{self.worker_profile.ssn}'
        )
        self.assertTrue(worker_exists_response.get('WorkerExists'))

        # Fetch worker details
        worker_number = worker_exists_response.get('WorkerNumber')
        worker_details = Link2PrismaService._make_request(
            method='GET',
            endpoint=f'worker/{worker_number}'
        )
        
        # Verify worker details
        self.assertEqual(worker_details.get('Name'), self.worker.last_name)
        self.assertEqual(worker_details.get('Firstname'), self.worker.first_name)
        self.assertEqual(worker_details.get('INSS'), self.worker_profile.ssn)

    def test_job_approval_flow(self):
        """Test the job approval flow"""
        # Check if Link2Prisma is properly configured
        try:
            Link2PrismaService.test_connection()
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

        # First ensure worker exists in Link2Prisma
        Link2PrismaService.sync_worker(self.worker)

        # Test job approval
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertTrue(result)

        # Test job cancellation
        result = Link2PrismaService.handle_job_cancellation(self.job_application)
        self.assertTrue(result)

    def test_sync_worker_data(self):
        """Test the worker data sync functionality"""
        # Check if Link2Prisma is properly configured
        try:
            Link2PrismaService.test_connection()
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

    def tearDown(self):
        """Clean up test data"""
        # Cancel any active declarations
        try:
            Link2PrismaService.handle_job_cancellation(self.job_application)
        except:
            pass

        # Clean up database
        self.job_application.delete()
        self.job.delete()
        self.worker.delete()
        self.customer.delete()
        self.address.delete()
        self.job_address.delete()
        self.application_address.delete()