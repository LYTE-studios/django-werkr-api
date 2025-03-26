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


class TestLink2PrismaServiceMock(TestCase):
    def setUp(self):
        # Create test user with worker profile
        self.user = User.objects.create(
            email="test@test.com",
            first_name="Test",
            last_name="Worker",
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
    def test_handle_job_approval(self, mock_make_request):
        # Mock successful response
        mock_make_request.return_value = {'status': 'success'}

        # Test job approval
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertTrue(result)

        # Verify the request was made with correct data
        mock_make_request.assert_called_once()
        args = mock_make_request.call_args
        self.assertEqual(args[1]['method'], 'POST')
        self.assertEqual(args[1]['endpoint'], 'declarations')
        
        # Verify request data
        data = args[1]['data']
        self.assertEqual(data['NatureDeclaration'], 'DimonaIn')
        self.assertEqual(data['ContractType'], 'Normal')
        self.assertEqual(data['Email'], self.user.email)
        self.assertEqual(data['Name'], self.user.last_name)
        self.assertEqual(data['Firstname'], self.user.first_name)
        self.assertEqual(data['INSS'], self.worker_profile.ssn)
        self.assertEqual(data['WorkerType'], 'STU')  # Student type
        self.assertEqual(data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)
        
        # Verify date and time fields
        self.assertEqual(data['StartingDate'], self.job.start_time.strftime("%Y%m%d"))
        self.assertEqual(data['EndingDate'], self.job.end_time.strftime("%Y%m%d"))
        self.assertEqual(data['StartingHour'], self.job.start_time.strftime("%Y%m%d%H%M"))
        self.assertEqual(data['EndingHour'], self.job.end_time.strftime("%Y%m%d%H%M"))
        
        # Verify planned hours
        expected_hours = int((self.job.end_time - self.job.start_time).total_seconds() / 3600)
        self.assertEqual(data['PlannedHoursNbr'], expected_hours)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_handle_job_cancellation(self, mock_make_request):
        # Mock successful response
        mock_make_request.return_value = {'status': 'success'}

        # Test job cancellation
        result = Link2PrismaService.handle_job_cancellation(self.job_application)
        self.assertTrue(result)

        # Verify the request was made with correct data
        mock_make_request.assert_called_once()
        args = mock_make_request.call_args
        self.assertEqual(args[1]['method'], 'POST')
        self.assertEqual(args[1]['endpoint'], 'declarations')
        
        # Verify request data
        data = args[1]['data']
        self.assertEqual(data['NatureDeclaration'], 'DimonaCancel')
        self.assertEqual(data['DimonaPeriodId'], self.job_application.id)
        self.assertEqual(data['Email'], self.user.email)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_sync_worker_data_new_worker(self, mock_make_request):
        # Mock responses for worker exists check and creation
        mock_make_request.side_effect = [
            {'WorkerExists': False},  # Worker doesn't exist yet
            {'status': 'success'}     # Worker creation successful
        ]

        # Test worker sync
        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Verify the requests were made
        self.assertEqual(mock_make_request.call_count, 2)
        
        # Verify worker exists check
        exists_call = mock_make_request.call_args_list[0]
        self.assertEqual(exists_call[1]['method'], 'GET')
        self.assertEqual(exists_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')

        # Verify worker creation
        create_call = mock_make_request.call_args_list[1]
        self.assertEqual(create_call[1]['method'], 'POST')
        self.assertEqual(create_call[1]['endpoint'], 'worker')
        # Verify worker data
        worker_data = create_call[1]['data']
        self.assertEqual(worker_data['Name'], self.user.last_name)
        self.assertEqual(worker_data['Firstname'], self.user.first_name)
        self.assertEqual(worker_data['INSS'], self.worker_profile.ssn)
        self.assertEqual(worker_data['Birthdate'], self.worker_profile.date_of_birth.strftime("%Y%m%d"))
        self.assertEqual(worker_data['Birthplace'], self.worker_profile.place_of_birth)
        self.assertEqual(worker_data['BankAccount'], self.worker_profile.iban)
        self.assertEqual(worker_data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)
        
        # Verify address data
        self.assertEqual(len(worker_data['address']), 1)
        address = worker_data['address'][0]
        self.assertEqual(address['Street'], self.address.street_name)
        self.assertEqual(address['HouseNumber'], self.address.house_number)
        self.assertEqual(address['ZIPCode'], self.address.zip_code)
        self.assertEqual(address['City'], self.address.city)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_sync_worker_data_existing_worker(self, mock_make_request):
        # Mock responses for worker exists check and update
        mock_make_request.side_effect = [
            {'WorkerExists': True, 'WorkerNumber': '12345'},  # Worker exists
            {'status': 'success'}     # Worker update successful
        ]

        # Test worker sync
        result = Link2PrismaService.sync_worker_data()
        self.assertTrue(result)

        # Verify the requests were made
        self.assertEqual(mock_make_request.call_count, 2)
        
        # Verify worker exists check
        exists_call = mock_make_request.call_args_list[0]
        self.assertEqual(exists_call[1]['method'], 'GET')
        self.assertEqual(exists_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')

        # Verify worker update
        update_call = mock_make_request.call_args_list[1]
        self.assertEqual(update_call[1]['method'], 'PUT')
        self.assertEqual(update_call[1]['endpoint'], 'worker/12345')

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_connection_success(self, mock_make_request):
        # Mock successful health check response
        mock_make_request.return_value = {'status': 'healthy'}

        # Test connection
        result = Link2PrismaService.test_connection()
        self.assertTrue(result)

        # Verify the request was made correctly
        mock_make_request.assert_called_once_with(
            method='GET',
            endpoint='health'
        )

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_connection_failure(self, mock_make_request):
        # Mock failed health check
        mock_make_request.side_effect = Exception("Connection failed")

        # Test connection
        result = Link2PrismaService.test_connection()
        self.assertFalse(result)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_error_handling_api_error(self, mock_make_request):
        # Mock API error response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_make_request.side_effect = Exception(f"Link2Prisma API error: 400 - Bad Request")

        # Test error handling with API error
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertFalse(result)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_error_handling_network_error(self, mock_make_request):
        # Mock network error
        mock_make_request.side_effect = Exception("Connection timeout")

        # Test error handling with network error
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertFalse(result)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_error_handling_invalid_data(self, mock_make_request):
        # Mock error with invalid data
        mock_make_request.side_effect = Exception("Invalid data format")

        # Test error handling with invalid data
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertFalse(result)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    @patch('apps.notifications.managers.notification_manager.NotificationManager.notify_admin')
    def test_error_notification_job_approval(self, mock_notify_admin, mock_make_request):
        # Mock API error
        error_message = "API Error"
        mock_make_request.side_effect = Exception(error_message)

        # Test job approval error
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertFalse(result)

        # Verify admin notification was sent
        mock_notify_admin.assert_called_once_with(
            'Link2Prisma Job Approval Error',
            f'Failed to send job approval to Link2Prisma: {error_message}'
        )

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    @patch('apps.notifications.managers.notification_manager.NotificationManager.notify_admin')
    def test_error_notification_job_cancellation(self, mock_notify_admin, mock_make_request):
        # Mock API error
        error_message = "API Error"
        mock_make_request.side_effect = Exception(error_message)

        # Test job cancellation error
        result = Link2PrismaService.handle_job_cancellation(self.job_application)
        self.assertFalse(result)

        # Verify admin notification was sent
        mock_notify_admin.assert_called_once_with(
            'Link2Prisma Job Cancellation Error',
            f'Failed to send job cancellation to Link2Prisma: {error_message}'
        )

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    @patch('apps.notifications.managers.notification_manager.NotificationManager.notify_admin')
    def test_error_notification_worker_sync(self, mock_notify_admin, mock_make_request):
        # Mock API error
        error_message = "API Error"
        mock_make_request.side_effect = Exception(error_message)

        # Test worker sync error
        result = Link2PrismaService.sync_worker_data()
        self.assertFalse(result)

        # Verify admin notification was sent
        mock_notify_admin.assert_called_once_with(
            'Worker Sync Failed',
            f'Worker sync task failed: {error_message}'
        )