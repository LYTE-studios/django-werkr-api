from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta, date
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.jobs.models import Job, JobApplication, JobApplicationState, JobState
from apps.jobs.services.contract_service import JobApplicationService
from apps.authentication.utils.worker_util import WorkerUtil
from apps.legal.services.link2prisma_service import Link2PrismaService

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a mock job and assign worker with SSN 04042306169 to test ContractService approval'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ssn',
            type=str,
            default='04042306169',
            help='SSN of the worker to assign (default: 04042306169)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up created test data after completion'
        )

    def handle(self, *args, **options):
        ssn = options['ssn']
        cleanup = options['cleanup']
        
        self.stdout.write(f"🔍 Looking for worker with SSN: {ssn}")
        
        try:
            # Always create a fresh test worker to avoid modifying existing users
            self.stdout.write(f'🔧 Creating test worker with SSN: {ssn}')
            worker = self.create_test_worker(ssn)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created test worker: {worker.first_name} {worker.last_name}')
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Found worker: {worker.first_name} {worker.last_name} (ID: {worker.id})')
            )
            
            # Check worker profile completion
            completion_data = WorkerUtil.calculate_worker_completion(worker)
            completion_percentage = completion_data[0]
            missing_fields = completion_data[1]
            
            self.stdout.write(f"📊 Worker profile completion: {completion_percentage}%")
            if missing_fields:
                self.stdout.write(f"⚠️  Missing fields: {', '.join(missing_fields)}")
            
            # Create a customer user for the job
            customer = self.create_mock_customer()
            self.stdout.write(f"👤 Created mock customer: {customer.email}")
            
            # Create mock job
            job = self.create_mock_job(customer)
            self.stdout.write(f"💼 Created mock job: {job.title} (ID: {job.id})")
            
            # Create worker address for application
            worker_address = self.create_mock_worker_address()
            self.stdout.write(f"📍 Created worker address: {worker_address.to_readable()}")
            
            # Create job application
            application = self.create_job_application(job, worker, worker_address)
            self.stdout.write(f"📝 Created job application (ID: {application.id})")
            
            # First sync worker to Link2Prisma (create if doesn't exist)
            self.stdout.write("🔄 Syncing worker to Link2Prisma...")
            try:
                Link2PrismaService.sync_worker(worker)
                self.stdout.write("✅ Worker synced to Link2Prisma")
            except Exception as e:
                self.stdout.write(f"⚠️  Worker sync warning: {str(e)}")
            
            # Test the approval process
            self.stdout.write("🚀 Testing ContractService approval...")
            
            try:
                JobApplicationService.approve_application(application.id)
                
                # Refresh application from database
                application.refresh_from_db()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Application approved successfully!')
                )
                self.stdout.write(f"📋 Application state: {application.application_state}")
                
                # Check if Dimona was created (this would be logged in the service)
                self.stdout.write("🏛️  Dimona declaration should have been created in Link2Prisma")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Approval failed: {str(e)}')
                )
                
                # Still show the application details for debugging
                application.refresh_from_db()
                self.stdout.write(f"📋 Application state: {application.application_state}")
            
            # Display summary
            self.display_summary(worker, job, application)
            
            # Cleanup if requested
            if cleanup:
                # Clean up all test data including the test worker
                self.cleanup_test_data(customer, job, application, worker_address, worker)
                self.stdout.write(self.style.SUCCESS("🧹 Test data cleaned up"))
            else:
                self.stdout.write("💡 Use --cleanup flag to remove test data")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error during test: {str(e)}')
            )

    def create_test_worker(self, ssn):
        """Create a complete test worker with the specified SSN"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # Create worker address first
        worker_address = Address.objects.create(
            street_name='Test Worker Street',
            house_number='789',
            city='Ghent',
            zip_code='9000',
            country='Belgium',
            latitude=51.0543,  # Ghent coordinates
            longitude=3.7174
        )
        
        # Create user with unique username
        worker = User.objects.create_user(
            username=f'test_worker_{unique_id}',
            email=f'test_worker_{unique_id}@example.com',
            first_name='Test',
            last_name='Worker',
            is_active=True
        )
        
        # Create complete worker profile
        WorkerProfile.objects.create(
            user=worker,
            ssn=ssn,
            iban='BE68539007547034',  # Valid Belgian IBAN format
            worker_address=worker_address,
            date_of_birth=date(1990, 4, 23),  # Based on SSN format
            place_of_birth='Brussels',
            accepted=True,
            hours=20.0,
            worker_type=WorkerProfile.WorkerType.STUDENT,
            has_passed_onboarding=True
        )
        
        return worker

    def create_mock_customer(self):
        """Create a mock customer user for the job"""
        customer = User.objects.create_user(
            username=f'test_customer_{timezone.now().timestamp()}',
            email=f'test_customer_{timezone.now().timestamp()}@example.com',
            first_name='Test',
            last_name='Customer',
            is_active=True
        )
        return customer

    def create_mock_job(self, customer):
        """Create a mock job"""
        # Create job address
        job_address = Address.objects.create(
            street_name='Test Street',
            house_number='123',
            city='Brussels',
            zip_code='1000',
            country='Belgium',
            latitude=50.8503,  # Brussels coordinates
            longitude=4.3517
        )
        
        now = timezone.now()
        
        job = Job.objects.create(
            customer=customer,
            title='Test Job for Contract Approval',
            description='This is a test job to verify the contract approval process',
            address=job_address,
            job_state=JobState.pending,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=8),
            application_start_time=now - timedelta(hours=1),  # Started 1 hour ago
            application_end_time=now + timedelta(hours=23),   # Ends in 23 hours
            created_at=now,
            is_draft=False,
            archived=False,
            max_workers=5,
            selected_workers=0
        )
        
        return job

    def create_mock_worker_address(self):
        """Create a mock address for the worker application"""
        address = Address.objects.create(
            street_name='Worker Street',
            house_number='456',
            city='Antwerp',
            zip_code='2000',
            country='Belgium',
            latitude=51.2194,  # Antwerp coordinates
            longitude=4.4025
        )
        return address

    def create_job_application(self, job, worker, address):
        """Create a job application"""
        now = timezone.now()
        
        application = JobApplication.objects.create(
            job=job,
            worker=worker,
            address=address,
            application_state=JobApplicationState.pending,
            no_travel_cost=False,
            created_at=now,
            modified_at=now,
            note='Test application for contract approval'
        )
        
        return application

    def display_summary(self, worker, job, application):
        """Display a summary of the test"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📊 TEST SUMMARY")
        self.stdout.write("="*60)
        self.stdout.write(f"Worker: {worker.first_name} {worker.last_name}")
        self.stdout.write(f"SSN: {worker.worker_profile.ssn}")
        self.stdout.write(f"Worker Type: {worker.worker_profile.worker_type}")
        self.stdout.write(f"Job: {job.title}")
        self.stdout.write(f"Job State: {job.job_state}")
        self.stdout.write(f"Application State: {application.application_state}")
        self.stdout.write(f"Distance: {application.distance} km" if application.distance else "Distance: Not calculated")
        self.stdout.write("="*60)

    def cleanup_test_data(self, customer, job, application, worker_address, test_worker=None):
        """Clean up the test data - only removes test objects, never existing users"""
        try:
            # Delete in reverse order of dependencies
            application.delete()
            job.address.delete()  # Delete job address
            job.delete()
            worker_address.delete()
            customer.delete()
            
            # Delete test worker and related data
            if test_worker and test_worker.username.startswith('test_worker_'):
                test_worker_address = test_worker.worker_profile.worker_address
                test_worker.worker_profile.delete()
                test_worker.delete()
                if test_worker_address:
                    test_worker_address.delete()
        except Exception as e:
            # If cleanup fails, just log it - don't crash the test
            print(f"⚠️  Cleanup warning: {str(e)}")