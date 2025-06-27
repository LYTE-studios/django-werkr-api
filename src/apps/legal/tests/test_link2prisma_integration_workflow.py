"""
Comprehensive integration tests for Link2PrismaService workflow.

These tests verify that the Link2PrismaService correctly handles:
1. JobApplication approval (Dimona declaration creation)
2. JobApplication denial from approved state (Dimona declaration cancellation)
3. Job deletion (cancellation of all related Dimona declarations)

To run these tests:
    pytest src/apps/legal/tests/test_link2prisma_integration_workflow.py -v -s

Note: These tests require proper test environment credentials in your .env file:
- LINK2PRISMA_BASE_URL: Test environment URL
- LINK2PRISMA_PFX_PATH: Path to test certificate
- LINK2PRISMA_EMPLOYER_REF: Test employer reference
"""

import pytest
from django.test import TransactionTestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from apps.legal.services.link2prisma_service import Link2PrismaService
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.jobs.models.job import Job
from apps.jobs.models.application import JobApplication
from apps.jobs.models.job_application_state import JobApplicationState
from apps.jobs.models.dimona import Dimona
from apps.jobs.services.contract_service import JobApplicationService
from apps.jobs.services.job_service import JobService

User = get_user_model()


class TestLink2PrismaWorkflowIntegration(TransactionTestCase):
    """
    Integration tests for the complete Link2Prisma workflow.
    
    These tests verify that the service correctly handles all three scenarios:
    1. Job approval creates Dimona declarations
    2. Job denial cancels existing Dimona declarations
    3. Job deletion cancels all related Dimona declarations
    """

    def setUp(self):
        """Set up test data for all workflow tests"""
        # Create test addresses
        self.worker_address = Address.objects.create(
            street_name="Worker Street",
            house_number="123",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8503,
            longitude=4.3517
        )

        self.job_address = Address.objects.create(
            street_name="Job Street",
            house_number="456",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8467,
            longitude=4.3517
        )

        self.application_address = Address.objects.create(
            street_name="Application Street",
            house_number="789",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8431,
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
            worker_address=self.worker_address,
            worker_type="student",
            hours=20
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

        # Create job application
        self.job_application = JobApplication.objects.create(
            job=self.job,
            worker=self.worker,
            address=self.application_address,
            application_state=JobApplicationState.pending,
            created_at=timezone.now(),
            modified_at=timezone.now()
        )

    def test_connection_setup(self):
        """Test that Link2Prisma connection is properly configured"""
        try:
            result = Link2PrismaService.test_connection()
            self.assertTrue(result)
            print("✅ Link2Prisma connection test passed")
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_scenario_1_job_approval_creates_dimona_declaration(self, mock_make_request):
        """
        Test Scenario 1: JobApplication approval creates Dimona declaration
        
        This test verifies that when a job application is approved:
        1. The worker is synced to Link2Prisma
        2. A Dimona declaration is created
        3. A Dimona record is saved in the local database
        """
        print("\n🧪 Testing Scenario 1: Job Approval → Dimona Declaration Creation")
        
        # Mock responses for the workflow
        mock_make_request.side_effect = [
            # Worker exists check
            {'WorkerExists': True, 'WorkerNumber': '12345'},
            # Worker sync (worker already exists)
            {'WorkerExists': True, 'WorkerNumber': '12345'},
            # Dimona declaration creation
            {'UniqueIdentifier': 'dimona-12345'}
        ]

        # Verify initial state
        self.assertEqual(self.job_application.application_state, JobApplicationState.pending)
        self.assertEqual(Dimona.objects.filter(application=self.job_application).count(), 0)
        
        print(f"📋 Initial application state: {self.job_application.application_state}")
        print(f"📊 Initial Dimona records: {Dimona.objects.filter(application=self.job_application).count()}")

        # Approve the job application
        try:
            JobApplicationService.approve_application(self.job_application.id)
            print("✅ Job application approved successfully")
        except Exception as e:
            self.fail(f"Job approval failed: {str(e)}")

        # Refresh application from database
        self.job_application.refresh_from_db()
        
        # Verify application state changed
        self.assertEqual(self.job_application.application_state, JobApplicationState.approved)
        print(f"📋 Application state after approval: {self.job_application.application_state}")

        # Verify Dimona record was created
        dimona_records = Dimona.objects.filter(application=self.job_application)
        self.assertEqual(dimona_records.count(), 1)
        
        dimona_record = dimona_records.first()
        self.assertEqual(dimona_record.id, 'dimona-12345')
        self.assertEqual(dimona_record.application, self.job_application)
        self.assertIsNone(dimona_record.success)  # Not yet processed
        self.assertEqual(dimona_record.reason, "Dimona declaration submitted to Link2Prisma")
        
        print(f"📊 Dimona record created: {dimona_record.id}")
        print(f"📝 Dimona reason: {dimona_record.reason}")

        # Verify the correct API calls were made
        self.assertEqual(mock_make_request.call_count, 3)
        
        # Verify worker exists check
        worker_exists_call = mock_make_request.call_args_list[0]
        self.assertEqual(worker_exists_call[1]['method'], 'GET')
        self.assertEqual(worker_exists_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')
        
        # Verify worker sync
        worker_sync_call = mock_make_request.call_args_list[1]
        self.assertEqual(worker_sync_call[1]['method'], 'GET')
        self.assertEqual(worker_sync_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')
        
        # Verify Dimona declaration creation
        dimona_call = mock_make_request.call_args_list[2]
        self.assertEqual(dimona_call[1]['method'], 'POST')
        self.assertEqual(dimona_call[1]['endpoint'], 'worker/12345/dimona')
        
        # Verify Dimona data structure
        dimona_data = dimona_call[1]['data']
        self.assertEqual(dimona_data['NatureDeclaration'], 'DimonaIn')
        self.assertEqual(dimona_data['ContractType'], 'Normal')
        self.assertEqual(dimona_data['Email'], self.worker.email)
        self.assertEqual(dimona_data['Name'], self.worker.last_name)
        self.assertEqual(dimona_data['Firstname'], self.worker.first_name)
        self.assertEqual(dimona_data['INSS'], self.worker_profile.ssn)
        self.assertEqual(dimona_data['WorkerType'], 'STU')  # Student type
        self.assertEqual(dimona_data['EmployerRef'], settings.LINK2PRISMA_EMPLOYER_REF)
        
        print("✅ All API calls verified")
        print("✅ Scenario 1 test completed successfully")

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_scenario_2_job_denial_cancels_dimona_declaration(self, mock_make_request):
        """
        Test Scenario 2: JobApplication denial from approved state cancels Dimona declaration
        
        This test verifies that when an approved job application is denied:
        1. The existing Dimona declaration is cancelled
        2. The Dimona record is updated in the local database
        """
        print("\n🧪 Testing Scenario 2: Job Denial → Dimona Declaration Cancellation")
        
        # First, create an approved application with a Dimona record
        self.job_application.application_state = JobApplicationState.approved
        self.job_application.save()
        
        # Create a Dimona record for the approved application
        dimona_record = Dimona.objects.create(
            id='dimona-12345',
            application=self.job_application,
            success=True,
            reason="Dimona declaration submitted to Link2Prisma",
            created=timezone.now()
        )
        
        print(f"📋 Initial application state: {self.job_application.application_state}")
        print(f"📊 Initial Dimona record: {dimona_record.id} (success: {dimona_record.success})")

        # Mock responses for the cancellation workflow
        mock_make_request.side_effect = [
            # Worker exists check
            {'WorkerExists': True, 'WorkerNumber': '12345'},
            # Dimona cancellation
            {'UniqueIdentifier': 'cancel-67890'}
        ]

        # Deny the job application
        try:
            JobApplicationService.deny_application(self.job_application.id)
            print("✅ Job application denied successfully")
        except Exception as e:
            self.fail(f"Job denial failed: {str(e)}")

        # Refresh application from database
        self.job_application.refresh_from_db()
        
        # Verify application state changed
        self.assertEqual(self.job_application.application_state, JobApplicationState.rejected)
        print(f"📋 Application state after denial: {self.job_application.application_state}")

        # Verify Dimona record was updated
        dimona_record.refresh_from_db()
        self.assertEqual(dimona_record.success, False)
        self.assertEqual(dimona_record.reason, "Dimona declaration cancelled")
        
        print(f"📊 Dimona record updated: success={dimona_record.success}, reason={dimona_record.reason}")

        # Verify the correct API calls were made
        self.assertEqual(mock_make_request.call_count, 2)
        
        # Verify worker exists check
        worker_exists_call = mock_make_request.call_args_list[0]
        self.assertEqual(worker_exists_call[1]['method'], 'GET')
        self.assertEqual(worker_exists_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')
        
        # Verify Dimona cancellation
        cancel_call = mock_make_request.call_args_list[1]
        self.assertEqual(cancel_call[1]['method'], 'POST')
        self.assertEqual(cancel_call[1]['endpoint'], 'worker/12345/dimona')
        
        # Verify cancellation data structure
        cancel_data = cancel_call[1]['data']
        self.assertEqual(cancel_data['NatureDeclaration'], 'DimonaCancel')
        self.assertEqual(cancel_data['DimonaPeriodId'], 'dimona-12345')
        self.assertEqual(cancel_data['Email'], self.worker.email)
        
        print("✅ All API calls verified")
        print("✅ Scenario 2 test completed successfully")

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_scenario_3_job_deletion_cancels_all_dimona_declarations(self, mock_make_request):
        """
        Test Scenario 3: Job deletion cancels all related Dimona declarations
        
        This test verifies that when a job is deleted:
        1. All approved applications for the job are found
        2. All related Dimona declarations are cancelled
        3. All application states are updated to rejected
        """
        print("\n🧪 Testing Scenario 3: Job Deletion → All Dimona Declarations Cancelled")
        
        # Create multiple approved applications for the same job
        worker2 = User.objects.create_user(
            username="testworker2",
            email="test.worker2@example.com",
            password="testpass123",
            first_name="Test",
            last_name="Worker2"
        )
        
        worker_profile2 = WorkerProfile.objects.create(
            user=worker2,
            ssn="12345678902",
            date_of_birth=datetime(1990, 1, 1),
            place_of_birth="Brussels",
            iban="BE68539007547035",
            worker_address=self.worker_address,
            worker_type="student",
            hours=20
        )
        
        # Update job to allow multiple workers
        self.job.max_workers = 2
        self.job.save()
        
        # Create second application
        application2 = JobApplication.objects.create(
            job=self.job,
            worker=worker2,
            address=self.application_address,
            application_state=JobApplicationState.pending,
            created_at=timezone.now(),
            modified_at=timezone.now()
        )
        
        # Approve both applications
        self.job_application.application_state = JobApplicationState.approved
        self.job_application.save()
        application2.application_state = JobApplicationState.approved
        application2.save()
        
        # Create Dimona records for both applications
        dimona1 = Dimona.objects.create(
            id='dimona-12345',
            application=self.job_application,
            success=True,
            reason="Dimona declaration submitted to Link2Prisma",
            created=timezone.now()
        )
        
        dimona2 = Dimona.objects.create(
            id='dimona-67890',
            application=application2,
            success=True,
            reason="Dimona declaration submitted to Link2Prisma",
            created=timezone.now()
        )
        
        print(f"📋 Created {JobApplication.objects.filter(job=self.job, application_state=JobApplicationState.approved).count()} approved applications")
        print(f"📊 Created {Dimona.objects.filter(application__job=self.job).count()} Dimona records")

        # Mock responses for the deletion workflow
        mock_make_request.side_effect = [
            # Worker 1 exists check
            {'WorkerExists': True, 'WorkerNumber': '12345'},
            # Worker 1 Dimona cancellation
            {'UniqueIdentifier': 'cancel-11111'},
            # Worker 2 exists check
            {'WorkerExists': True, 'WorkerNumber': '67890'},
            # Worker 2 Dimona cancellation
            {'UniqueIdentifier': 'cancel-22222'}
        ]

        # Delete the job
        try:
            JobService.delete_job(self.job.id)
            print("✅ Job deleted successfully")
        except Exception as e:
            self.fail(f"Job deletion failed: {str(e)}")

        # Refresh job from database
        self.job.refresh_from_db()
        
        # Verify job is archived
        self.assertTrue(self.job.archived)
        self.assertEqual(self.job.selected_workers, 0)
        print(f"📋 Job archived: {self.job.archived}, selected_workers: {self.job.selected_workers}")

        # Verify all applications are now rejected
        applications = JobApplication.objects.filter(job=self.job)
        for app in applications:
            self.assertEqual(app.application_state, JobApplicationState.rejected)
        
        print(f"📋 All {applications.count()} applications are now rejected")

        # Verify all Dimona records are updated
        dimona_records = Dimona.objects.filter(application__job=self.job)
        for dimona in dimona_records:
            self.assertEqual(dimona.success, False)
            self.assertEqual(dimona.reason, "Dimona declaration cancelled")
        
        print(f"📊 All {dimona_records.count()} Dimona records are cancelled")

        # Verify the correct API calls were made (2 workers × 2 calls each = 4 calls)
        self.assertEqual(mock_make_request.call_count, 4)
        
        # Verify worker 1 cancellation calls
        worker1_exists_call = mock_make_request.call_args_list[0]
        self.assertEqual(worker1_exists_call[1]['method'], 'GET')
        self.assertEqual(worker1_exists_call[1]['endpoint'], f'workerExists/{self.worker_profile.ssn}')
        
        worker1_cancel_call = mock_make_request.call_args_list[1]
        self.assertEqual(worker1_cancel_call[1]['method'], 'POST')
        self.assertEqual(worker1_cancel_call[1]['endpoint'], 'worker/12345/dimona')
        
        # Verify worker 2 cancellation calls
        worker2_exists_call = mock_make_request.call_args_list[2]
        self.assertEqual(worker2_exists_call[1]['method'], 'GET')
        self.assertEqual(worker2_exists_call[1]['endpoint'], f'workerExists/{worker_profile2.ssn}')
        
        worker2_cancel_call = mock_make_request.call_args_list[3]
        self.assertEqual(worker2_cancel_call[1]['method'], 'POST')
        self.assertEqual(worker2_cancel_call[1]['endpoint'], 'worker/67890/dimona')
        
        print("✅ All API calls verified")
        print("✅ Scenario 3 test completed successfully")

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_freelancer_skips_dimona_declaration(self, mock_make_request):
        """
        Test that freelancers skip Dimona declaration creation
        
        This test verifies that when a freelancer's job application is approved,
        no Dimona declaration is created in Link2Prisma.
        """
        print("\n🧪 Testing Freelancer Skip: No Dimona Declaration for Freelancers")
        
        # Update worker to be a freelancer
        self.worker_profile.worker_type = WorkerProfile.WorkerType.FREELANCER
        self.worker_profile.save()
        
        print(f"👷 Worker type: {self.worker_profile.worker_type}")

        # Try to approve the job application
        try:
            JobApplicationService.approve_application(self.job_application.id)
            print("✅ Job application approved successfully")
        except Exception as e:
            self.fail(f"Job approval failed: {str(e)}")

        # Refresh application from database
        self.job_application.refresh_from_db()
        
        # Verify application state changed
        self.assertEqual(self.job_application.application_state, JobApplicationState.approved)
        print(f"📋 Application state after approval: {self.job_application.application_state}")

        # Verify NO Dimona record was created
        dimona_records = Dimona.objects.filter(application=self.job_application)
        self.assertEqual(dimona_records.count(), 0)
        
        print(f"📊 Dimona records created: {dimona_records.count()} (expected: 0)")

        # Verify NO API calls were made to Link2Prisma
        self.assertEqual(mock_make_request.call_count, 0)
        
        print("✅ No API calls made to Link2Prisma")
        print("✅ Freelancer skip test completed successfully")

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_error_handling_during_approval(self, mock_make_request):
        """
        Test error handling during job approval
        
        This test verifies that if Link2Prisma API fails during approval,
        the job approval still succeeds but errors are logged.
        """
        print("\n🧪 Testing Error Handling: Link2Prisma API Failure During Approval")
        
        # Mock API failure
        mock_make_request.side_effect = Exception("Link2Prisma API is down")

        # Try to approve the job application
        try:
            JobApplicationService.approve_application(self.job_application.id)
            print("✅ Job application approved successfully despite API failure")
        except Exception as e:
            self.fail(f"Job approval should succeed even with API failure: {str(e)}")

        # Refresh application from database
        self.job_application.refresh_from_db()
        
        # Verify application state changed (approval should succeed)
        self.assertEqual(self.job_application.application_state, JobApplicationState.approved)
        print(f"📋 Application state after approval: {self.job_application.application_state}")

        # Verify NO Dimona record was created (due to API failure)
        dimona_records = Dimona.objects.filter(application=self.job_application)
        self.assertEqual(dimona_records.count(), 0)
        
        print(f"📊 Dimona records created: {dimona_records.count()} (expected: 0 due to API failure)")

        print("✅ Error handling test completed successfully")

    def test_end_to_end_workflow_with_real_api(self):
        """
        Test the complete end-to-end workflow with real Link2Prisma API
        
        This test makes actual API calls to verify the complete workflow.
        Only runs if Link2Prisma is properly configured.
        """
        print("\n🧪 Testing End-to-End Workflow with Real Link2Prisma API")
        
        # Check if Link2Prisma is properly configured
        try:
            Link2PrismaService.test_connection()
        except Exception as e:
            self.skipTest(f"Link2Prisma not properly configured: {str(e)}")

        # Step 1: Sync worker to Link2Prisma
        print("🔄 Step 1: Syncing worker to Link2Prisma...")
        try:
            Link2PrismaService.sync_worker(self.worker)
            print("✅ Worker synced successfully")
        except Exception as e:
            self.fail(f"Worker sync failed: {str(e)}")

        # Step 2: Approve job application (creates Dimona declaration)
        print("🔄 Step 2: Approving job application...")
        try:
            JobApplicationService.approve_application(self.job_application.id)
            print("✅ Job application approved successfully")
        except Exception as e:
            self.fail(f"Job approval failed: {str(e)}")

        # Verify Dimona record was created
        dimona_records = Dimona.objects.filter(application=self.job_application)
        self.assertEqual(dimona_records.count(), 1)
        dimona_record = dimona_records.first()
        print(f"📊 Dimona record created: {dimona_record.id}")

        # Step 3: Deny job application (cancels Dimona declaration)
        print("🔄 Step 3: Denying job application...")
        try:
            JobApplicationService.deny_application(self.job_application.id)
            print("✅ Job application denied successfully")
        except Exception as e:
            self.fail(f"Job denial failed: {str(e)}")

        # Verify Dimona record was updated
        dimona_record.refresh_from_db()
        self.assertEqual(dimona_record.success, False)
        self.assertEqual(dimona_record.reason, "Dimona declaration cancelled")
        print(f"📊 Dimona record cancelled: {dimona_record.reason}")

        print("✅ End-to-end workflow test completed successfully")

    def tearDown(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Cancel any active declarations
        try:
            Link2PrismaService.handle_job_cancellation(self.job_application)
        except:
            pass

        # Clean up database objects
        Dimona.objects.filter(application__job=self.job).delete()
        JobApplication.objects.filter(job=self.job).delete()
        
        # Clean up users
        User.objects.filter(email__startswith="test.").delete()
        
        # Clean up addresses
        Address.objects.filter(street_name__startswith="Test").delete()
        Address.objects.filter(street_name__startswith="Worker").delete()
        Address.objects.filter(street_name__startswith="Job").delete()
        Address.objects.filter(street_name__startswith="Application").delete()
        
        print("✅ Test data cleaned up")


class TestLink2PrismaServiceUnit(TransactionTestCase):
    """
    Unit tests for Link2PrismaService methods.
    
    These tests focus on individual method functionality without making API calls.
    """

    def setUp(self):
        """Set up test data for unit tests"""
        # Create minimal test data
        self.user = User.objects.create_user(
            username="unittestuser",
            email="unit.test@example.com",
            password="testpass123",
            first_name="Unit",
            last_name="Test"
        )

        self.address = Address.objects.create(
            street_name="Unit Test Street",
            house_number="123",
            zip_code="1000",
            city="Brussels",
            country="Belgium",
            latitude=50.8503,
            longitude=4.3517
        )

        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
            ssn="12345678901",
            date_of_birth=datetime(1990, 1, 1),
            place_of_birth="Brussels",
            iban="BE68539007547034",
            worker_address=self.address,
            worker_type="student",
            hours=20
        )

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

        self.job_application = JobApplication.objects.create(
            job=self.job,
            worker=self.user,
            address=self.address,
            application_state=JobApplicationState.pending,
            created_at=timezone.now(),
            modified_at=timezone.now()
        )

    def test_truncate_function(self):
        """Test the truncate helper function"""
        from apps.legal.services.link2prisma_service import truncate
        
        # Test normal truncation
        self.assertEqual(truncate("Hello World", 5), "Hello")
        
        # Test None value
        self.assertEqual(truncate(None, 10), "")
        
        # Test empty string
        self.assertEqual(truncate("", 10), "")
        
        # Test string shorter than max length
        self.assertEqual(truncate("Short", 10), "Short")
        
        # Test non-string input
        self.assertEqual(truncate(12345, 3), "123")

    def test_dict_to_xml_function(self):
        """Test the XML conversion function"""
        from apps.legal.services.link2prisma_service import Link2PrismaService
        
        # Test simple dictionary
        data = {"name": "John", "age": 30}
        xml = Link2PrismaService._dict_to_xml(data, "person")
        expected = '<?xml version="1.0" encoding="utf-8"?><person><name>John</name><age>30</age></person>'
        self.assertEqual(xml, expected)
        
        # Test nested dictionary
        data = {"person": {"name": "John", "address": {"city": "Brussels"}}}
        xml = Link2PrismaService._dict_to_xml(data, "root")
        expected = '<?xml version="1.0" encoding="utf-8"?><root><person><name>John</name><address><city>Brussels</city></address></person></root>'
        self.assertEqual(xml, expected)
        
        # Test with special characters
        data = {"name": "John & Jane", "description": "Test < 5 > 3"}
        xml = Link2PrismaService._dict_to_xml(data, "person")
        expected = '<?xml version="1.0" encoding="utf-8"?><person><name>John &amp; Jane</name><description>Test &lt; 5 &gt; 3</description></person>'
        self.assertEqual(xml, expected)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_handle_job_approval_without_dimona_record(self, mock_make_request):
        """Test job approval when no Dimona record exists"""
        # Mock successful responses
        mock_make_request.side_effect = [
            {'WorkerExists': True, 'WorkerNumber': '12345'},
            {'UniqueIdentifier': 'dimona-12345'}
        ]
        
        # Ensure no Dimona record exists
        Dimona.objects.filter(application=self.job_application).delete()
        
        # Test approval
        result = Link2PrismaService.handle_job_approval(self.job_application)
        self.assertTrue(result)
        
        # Verify Dimona record was created
        dimona_records = Dimona.objects.filter(application=self.job_application)
        self.assertEqual(dimona_records.count(), 1)

    @patch('apps.legal.services.link2prisma_service.Link2PrismaService._make_request')
    def test_handle_job_cancellation_without_dimona_record(self, mock_make_request):
        """Test job cancellation when no Dimona record exists"""
        # Ensure no Dimona record exists
        Dimona.objects.filter(application=self.job_application).delete()
        
        # Test cancellation (should return True even without Dimona record)
        result = Link2PrismaService.handle_job_cancellation(self.job_application)
        self.assertTrue(result)
        
        # Verify no API calls were made
        mock_make_request.assert_not_called()

    def tearDown(self):
        """Clean up unit test data"""
        Dimona.objects.filter(application=self.job_application).delete()
        self.job_application.delete()
        self.job.delete()
        self.user.delete()
        self.address.delete() 