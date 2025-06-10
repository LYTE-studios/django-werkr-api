#!/usr/bin/env python
"""
Standalone script to test the contract approval flow.
This can be run directly or imported as a module.
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.jobs.models import Job, JobApplication, JobApplicationState, JobState
from apps.jobs.services.contract_service import JobApplicationService
from apps.authentication.utils.worker_util import WorkerUtil
from apps.legal.services.link2prisma_service import Link2PrismaService

User = get_user_model()


def test_contract_approval_flow(ssn='04042306169', cleanup=True):
    """
    Test the complete contract approval flow
    
    Args:
        ssn (str): SSN of the worker to test with
        cleanup (bool): Whether to clean up test data after completion
    
    Returns:
        dict: Test results
    """
    results = {
        'success': False,
        'worker_found': False,
        'job_created': False,
        'application_created': False,
        'approval_successful': False,
        'error': None,
        'worker_completion': 0,
        'missing_fields': []
    }
    
    created_objects = []
    
    try:
        print(f"🔍 Looking for worker with SSN: {ssn}")
        
        # Find worker with the specified SSN
        worker = User.objects.filter(
            worker_profile__ssn=ssn,
            is_active=True
        ).select_related('worker_profile').first()
        
        if not worker:
            print(f'⚠️  No worker found with SSN: {ssn}. Creating one...')
            worker = create_test_worker(ssn)
            created_objects.append(('test_worker', worker))
            created_objects.append(('test_worker_address', worker.worker_profile.worker_address))
            print(f'✅ Created test worker: {worker.first_name} {worker.last_name}')
        
        results['worker_found'] = True
        print(f'✅ Found worker: {worker.first_name} {worker.last_name} (ID: {worker.id})')
        
        # Check worker profile completion
        completion_data = WorkerUtil.calculate_worker_completion(worker)
        completion_percentage = completion_data[0]
        missing_fields = completion_data[1]
        
        results['worker_completion'] = completion_percentage
        results['missing_fields'] = missing_fields
        
        print(f"📊 Worker profile completion: {completion_percentage}%")
        if missing_fields:
            print(f"⚠️  Missing fields: {', '.join(missing_fields)}")
        
        # Create a customer user for the job
        customer = create_mock_customer()
        created_objects.append(('customer', customer))
        print(f"👤 Created mock customer: {customer.email}")
        
        # Create mock job
        job = create_mock_job(customer)
        created_objects.append(('job', job))
        created_objects.append(('job_address', job.address))
        results['job_created'] = True
        print(f"💼 Created mock job: {job.title} (ID: {job.id})")
        
        # Create worker address for application
        worker_address = create_mock_worker_address()
        created_objects.append(('worker_address', worker_address))
        print(f"📍 Created worker address: {worker_address.to_readable()}")
        
        # Create job application
        application = create_job_application(job, worker, worker_address)
        created_objects.append(('application', application))
        results['application_created'] = True
        print(f"📝 Created job application (ID: {application.id})")
        
        # First sync worker to Link2Prisma (create if doesn't exist)
        print("🔄 Syncing worker to Link2Prisma...")
        try:
            Link2PrismaService.sync_worker(worker)
            print("✅ Worker synced to Link2Prisma")
        except Exception as e:
            print(f"⚠️  Worker sync warning: {str(e)}")
        
        # Test the approval process
        print("🚀 Testing ContractService approval...")
        
        try:
            JobApplicationService.approve_application(application.id)
            
            # Refresh application from database
            application.refresh_from_db()
            
            results['approval_successful'] = True
            results['success'] = True
            print(f'✅ Application approved successfully!')
            print(f"📋 Application state: {application.application_state}")
            print("🏛️  Dimona declaration should have been created in Link2Prisma")
            
        except Exception as e:
            results['error'] = f'Approval failed: {str(e)}'
            print(f'❌ Approval failed: {str(e)}')
            
            # Still show the application details for debugging
            application.refresh_from_db()
            print(f"📋 Application state: {application.application_state}")
        
        # Display summary
        display_summary(worker, job, application)
        
    except Exception as e:
        results['error'] = f'Error during test: {str(e)}'
        print(f'❌ Error during test: {str(e)}')
    
    finally:
        # Cleanup if requested
        if cleanup and created_objects:
            cleanup_test_data(created_objects)
            print("🧹 Test data cleaned up")
    
    return results


def create_test_worker(ssn):
    """Create a test worker with the specified SSN"""
    # Create worker address
    worker_address = Address.objects.create(
        street_name='Test Worker Street',
        house_number='789',
        city='Ghent',
        zip_code='9000',
        country='Belgium',
        latitude=51.0543,  # Ghent coordinates
        longitude=3.7174
    )
    
    # Create user
    worker = User.objects.create_user(
        username=f'test_worker_{ssn}',
        email=f'test_worker_{ssn}@example.com',
        first_name='Test',
        last_name='Worker',
        is_active=True
    )
    
    # Create worker profile
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


def create_mock_customer():
    """Create a mock customer user for the job"""
    customer = User.objects.create_user(
        username=f'test_customer_{timezone.now().timestamp()}',
        email=f'test_customer_{timezone.now().timestamp()}@example.com',
        first_name='Test',
        last_name='Customer',
        is_active=True
    )
    return customer


def create_mock_job(customer):
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


def create_mock_worker_address():
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


def create_job_application(job, worker, address):
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


def display_summary(worker, job, application):
    """Display a summary of the test"""
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Worker: {worker.first_name} {worker.last_name}")
    print(f"SSN: {worker.worker_profile.ssn}")
    print(f"Worker Type: {worker.worker_profile.worker_type}")
    print(f"Job: {job.title}")
    print(f"Job State: {job.job_state}")
    print(f"Application State: {application.application_state}")
    print(f"Distance: {application.distance} km" if application.distance else "Distance: Not calculated")
    print("="*60)


def cleanup_test_data(created_objects):
    """Clean up the test data"""
    # Delete in reverse order of creation to handle dependencies
    for obj_type, obj in reversed(created_objects):
        try:
            obj.delete()
            print(f"🗑️  Deleted {obj_type}: {obj}")
        except Exception as e:
            print(f"⚠️  Failed to delete {obj_type}: {e}")


if __name__ == '__main__':
    # Run the test when script is executed directly
    import argparse
    
    parser = argparse.ArgumentParser(description='Test contract approval flow')
    parser.add_argument('--ssn', default='04042306169', help='SSN of worker to test')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup of test data')
    
    args = parser.parse_args()
    
    results = test_contract_approval_flow(
        ssn=args.ssn,
        cleanup=not args.no_cleanup
    )
    
    print(f"\n🎯 Test Results: {results}")
    
    if results['success']:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)