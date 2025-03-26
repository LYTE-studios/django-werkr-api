import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.conf import settings
from datetime import datetime, timedelta
from apps.authentication.models.user import User
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.jobs.models.job import Job
from apps.jobs.models.application import JobApplication
from apps.jobs.models.job_application_state import JobApplicationState
from apps.core.models.geo import Address
from apps.legal.services.link2prisma_service import Link2PrismaService


class TestLink2PrismaServiceIntegration(TestCase):
    def setUp(self):
        # Create test user with worker profile
        self.user = User.objects.create(
            email="test@test.com",
            first_name="Test",
            last_name="Worker",
            date_joined=timezone.now()
        )
        
        self.address = Address.objects.create(
            street_name="Test Street",
            house_number="123",
            city="Test City",
            zip_code="1000",
            country="Belgium",
            latitude=50.8503,
            longitude=4.3517
        )

        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
            worker_type=WorkerProfile.WorkerType.STUDENT,
            ssn="12345678901",
            iban="BE123456789",
            worker_address=self.address,
            date_of_birth=datetime(2000, 1, 1),
            place_of_birth="Brussels"
        )

        # Create test job
        self.job = Job.objects.create(
            customer=self.user,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=4),
            address=self.address,
            max_workers=1,
            selected_workers=0,
            application_start_time=timezone.now(),
            application_end_time=timezone.now() + timedelta(hours=12)
        )

        # Create job application
        self.job_application = JobApplication.objects.create(
            job=self.job,
            worker=self.user,
            address=self.address,
            application_state=JobApplicationState.pending,
            created_at=timezone.now(),
            modified_at=timezone.now()
        )

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_full_worker_lifecycle(self, mock_make_request):
        """Test the complete lifecycle of a worker in Link2Prisma"""
        
        # Step 1: Initial worker sync - worker doesn't exist
        mock_make_request.side_effect = [
            {'WorkerExists': False},  # Check if worker exists
            {'status': 'success', 'WorkerNumber': '12345'}  # Create worker response
        ]

        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Verify worker creation request
        create_call = mock_make_request.call_args_list[1]
        self.assertEqual(create_call[1]['method'], 'POST')
        self.assertEqual(create_call[1]['endpoint'], 'worker')

        worker_data = create_call[1]['data']
        self.assertEqual(worker_data['Name'], self.user.last_name)
        self.assertEqual(worker_data['Firstname'], self.user.first_name)
        self.assertEqual(worker_data['INSS'], self.worker_profile.ssn)
        self.assertEqual(worker_data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)

        # Step 2: Fetch worker to verify data
        mock_make_request.side_effect = [{
            'Name': self.user.last_name,
            'Firstname': self.user.first_name,
            'INSS': self.worker_profile.ssn,
            'EmployerRef': settings.LINK2PRISMA_EMPLOYER_REF,
            'WorkerNumber': '12345'
        }]

        fetched_worker = Link2PrismaService.fetch_worker(self.worker_profile.ssn)
        self.assertIsNotNone(fetched_worker)
        self.assertEqual(fetched_worker['INSS'], self.worker_profile.ssn)
        self.assertEqual(fetched_worker['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)

        # Step 3: Job approval
        mock_make_request.side_effect = [{'status': 'success'}]
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertTrue(result)

        # Verify job approval data
        approval_call = mock_make_request.call_args
        job_data = approval_call[1]['data']
        self.assertEqual(job_data['NatureDeclaration'], 'DimonaIn')
        self.assertEqual(job_data['ContractType'], 'Normal')
        self.assertEqual(job_data['INSS'], self.worker_profile.ssn)
        self.assertEqual(job_data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)
        self.assertEqual(
            job_data['PlannedHoursNbr'], 
            int((self.job.end_time - self.job.start_time).total_seconds() / 3600)
        )

        # Step 4: Job cancellation
        mock_make_request.side_effect = [{'status': 'success'}]
        result = Link2PrismaService.handle_job_cancellation(self.job_application)
        self.assertTrue(result)

        # Verify cancellation data
        cancel_call = mock_make_request.call_args
        cancel_data = cancel_call[1]['data']
        self.assertEqual(cancel_data['NatureDeclaration'], 'DimonaCancel')
        self.assertEqual(cancel_data['DimonaPeriodId'], self.job_application.id)
        self.assertEqual(cancel_data['Email'], self.user.email)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_worker_update_flow(self, mock_make_request):
        """Test updating an existing worker's data"""
        
        # Mock worker exists
        mock_make_request.side_effect = [
            {'WorkerExists': True, 'WorkerNumber': '12345'},  # Worker exists check
            {'status': 'success'}  # Update response
        ]

        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Verify update request
        update_call = mock_make_request.call_args_list[1]
        self.assertEqual(update_call[1]['method'], 'PUT')
        self.assertEqual(update_call[1]['endpoint'], 'worker/12345')

        # Verify updated data
        worker_data = update_call[1]['data']
        self.assertEqual(worker_data['Name'], self.user.last_name)
        self.assertEqual(worker_data['INSS'], self.worker_profile.ssn)
        self.assertEqual(worker_data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_error_handling_and_recovery(self, mock_make_request):
        """Test error handling and recovery scenarios"""
        
        # Test network error during worker fetch
        mock_make_request.side_effect = Exception("Network error")
        fetched_worker = Link2PrismaService.fetch_worker(self.worker_profile.ssn)
        self.assertIsNone(fetched_worker)

        # Test recovery after error
        mock_make_request.side_effect = [
            {'WorkerExists': True, 'WorkerNumber': '12345'},  # Worker exists
            {'status': 'success'}  # Successful update
        ]
        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Test API error response
        mock_make_request.side_effect = Exception("API Error: Invalid data")
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertFalse(result)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_edge_cases(self, mock_make_request):
        """Test edge cases and boundary conditions"""
        
        # Test with missing worker profile data
        self.worker_profile.date_of_birth = None
        self.worker_profile.save()

        mock_make_request.side_effect = [
            {'WorkerExists': False},
            {'status': 'success'}
        ]
        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Verify null handling
        worker_data = mock_make_request.call_args_list[1][1]['data']
        self.assertIsNone(worker_data['Birthdate'])

        # Test with very long job duration
        self.job.end_time = self.job.start_time + timedelta(days=7)
        self.job.save()

        mock_make_request.side_effect = [{'status': 'success'}]
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertTrue(result)

        # Verify long duration handling
        job_data = mock_make_request.call_args[1]['data']
        self.assertEqual(
            job_data['PlannedHoursNbr'], 
            int((self.job.end_time - self.job.start_time).total_seconds() / 3600)
        )