from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch
from datetime import datetime
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address

User = get_user_model()

class TestFetchPrismaWorkersCommand(TestCase):
    def setUp(self):
        self.out = StringIO()
        
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

        # Mock worker data from Link2Prisma
        self.mock_worker_data = {
            'WorkerNumber': '12345',
            'Name': 'Worker',
            'Firstname': 'Test',
            'INSS': '12345678901',
            'Status': 'Active',
            'LastSync': '20250326',
            'EmployerRef': '0719857388'
        }

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService.fetch_worker')
    def test_fetch_single_worker(self, mock_fetch):
        """Test fetching a single worker by SSN"""
        mock_fetch.return_value = self.mock_worker_data

        # Test table format
        call_command('fetch_prisma_workers', ssn='12345678901', stdout=self.out)
        output = self.out.getvalue()
        
        self.assertIn('12345', output)  # Worker number
        self.assertIn('Test Worker', output)  # Full name
        self.assertIn('12345678901', output)  # SSN
        self.assertIn('Active', output)  # Status
        self.assertIn('20250326', output)  # Last sync

        # Test JSON format
        self.out.truncate(0)
        self.out.seek(0)
        call_command('fetch_prisma_workers', ssn='12345678901', format='json', stdout=self.out)
        output = self.out.getvalue()
        
        self.assertIn('"WorkerNumber": "12345"', output)
        self.assertIn('"EmployerRef": "0719857388"', output)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService.fetch_worker')
    def test_fetch_all_workers(self, mock_fetch):
        """Test fetching all workers"""
        mock_fetch.return_value = self.mock_worker_data

        # Test table format
        call_command('fetch_prisma_workers', all=True, stdout=self.out)
        output = self.out.getvalue()
        
        self.assertIn('Total workers: 1', output)
        self.assertIn('12345', output)
        self.assertIn('Test Worker', output)

        # Test JSON format
        self.out.truncate(0)
        self.out.seek(0)
        call_command('fetch_prisma_workers', all=True, format='json', stdout=self.out)
        output = self.out.getvalue()
        
        self.assertIn('"WorkerNumber": "12345"', output)
        self.assertIn('"EmployerRef": "0719857388"', output)

    def test_missing_arguments(self):
        """Test command fails when no arguments provided"""
        call_command('fetch_prisma_workers', stdout=self.out)
        self.assertIn('Please provide either --ssn or --all option', self.out.getvalue())

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService.fetch_worker')
    def test_worker_not_found(self, mock_fetch):
        """Test handling of non-existent worker"""
        mock_fetch.return_value = None
        
        call_command('fetch_prisma_workers', ssn='nonexistent', stdout=self.out)
        self.assertIn('No worker found with SSN: nonexistent', self.out.getvalue())

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService.fetch_worker')
    def test_api_error_handling(self, mock_fetch):
        """Test handling of API errors"""
        mock_fetch.side_effect = Exception("API Error")
        
        call_command('fetch_prisma_workers', ssn='12345678901', stdout=self.out)
        self.assertIn('Error fetching worker data: API Error', self.out.getvalue())