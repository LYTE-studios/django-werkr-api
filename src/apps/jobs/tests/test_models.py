import datetime

from apps.core.models.geo import Address
from apps.core.utils.wire_names import *
from apps.jobs.models.application import JobApplication
from apps.jobs.models.job import Job
from apps.jobs.models.job_application_state import JobApplicationState
from apps.jobs.models.job_state import JobState
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.authentication.models import User
from apps.core.utils.wire_names import *


User = get_user_model()


class JobModelTest(TestCase):

    def setUp(self):
        self.address = Address.objects.create(
            street_name='123 Main St',
            city='Anytown',
            zip_code='12345',
            country='USA'
        )
        self.job = Job.objects.create(
            customer_id=1,
            title='Test Job',
            description='This is a test job.',
            address=self.address,
            job_state=JobState.pending,
            start_time=timezone.now() + datetime.timedelta(days=1),
            end_time=timezone.now() + datetime.timedelta(days=2),
            application_start_time=timezone.now() - datetime.timedelta(days=1),
            application_end_time=timezone.now() + datetime.timedelta(days=1),
            is_draft=False,
            archived=False,
            max_workers=10,
            selected_workers=5
        )

    def test_is_visible(self):
        self.assertTrue(self.job.is_visible())

    def test_is_not_visible_due_to_draft(self):
        self.job.is_draft = True
        self.assertFalse(self.job.is_visible())

    def test_is_not_visible_due_to_archived(self):
        self.job.archived = True
        self.assertFalse(self.job.is_visible())

    def test_is_not_visible_due_to_workers(self):
        self.job.selected_workers = 10
        self.assertFalse(self.job.is_visible())

    def test_is_not_visible_due_to_time_window(self):
        self.job.application_start_time = timezone.now() + datetime.timedelta(days=1)
        self.assertFalse(self.job.is_visible())


class JobApplicationModelTest(TestCase):

    def setUp(self):
        # Create an Address instance
        self.address = Address.objects.create(
            street_name='123 Main St',
            city='Anytown',
            zip_code='12345',
            country='USA',
            latitude=40.7128,  # Example latitude (New York)
            longitude=-74.0060  # Example longitude (New York)
        )

        # Create a User instance
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password'
        )

        # Create a Job instance
        self.job = Job.objects.create(
            customer=self.user,
            title='Test Job',
            description='This is a test job.',
            address=self.address,
            job_state=JobApplicationState.pending,
            start_time=timezone.now() + datetime.timedelta(days=1),
            end_time=timezone.now() + datetime.timedelta(days=2),
            application_start_time=timezone.now() - datetime.timedelta(days=1),
            application_end_time=timezone.now() + datetime.timedelta(days=1),
            is_draft=False,
            archived=False,
            max_workers=10,
            selected_workers=5
        )

        # Create a JobApplication instance with a pre-defined distance
        self.job_application_with_distance = JobApplication.objects.create(
            job=self.job,
            worker=self.user,
            address=self.address,
            application_state=JobApplicationState.pending,
            distance=10.0,  # Pre-defined distance
            no_travel_cost=True,
            created_at=timezone.now(),
            modified_at=timezone.now(),
            note='Test note'
        )

        # Create a JobApplication instance without a pre-defined distance
        self.job_application_without_distance = JobApplication(
            job=self.job,
            worker=self.user,
            address=self.address,
            application_state=JobApplicationState.pending,
            no_travel_cost=True,
            created_at=timezone.now(),
            modified_at=timezone.now(),
            note='Test note without distance'
        )
        self.job_application_without_distance.save()  # Distance will be calculated automatically

    def test_to_model_view(self):
        # Test the to_model_view method for the JobApplication with a pre-defined distance
        model_view = self.job_application_with_distance.to_model_view()
        self.assertEqual(model_view[k_id], self.job_application_with_distance.id)
        self.assertEqual(model_view[k_job][k_id], self.job.id)
        self.assertEqual(model_view[k_worker][k_id], self.user.id)
        self.assertEqual(model_view[k_address][k_id], self.address.id)
        self.assertEqual(model_view[k_state], JobApplicationState.pending)
        self.assertEqual(model_view[k_distance], 10.0)  # Pre-defined distance
        self.assertEqual(model_view[k_no_travel_cost], True)
        self.assertEqual(model_view[k_note], 'Test note')

        # Test the to_model_view method for the JobApplication without a pre-defined distance
        model_view = self.job_application_without_distance.to_model_view()
        self.assertEqual(model_view[k_id], self.job_application_without_distance.id)
        self.assertEqual(model_view[k_job][k_id], self.job.id)
        self.assertEqual(model_view[k_worker][k_id], self.user.id)
        self.assertEqual(model_view[k_address][k_id], self.address.id)
        self.assertEqual(model_view[k_state], JobApplicationState.pending)
        self.assertIsNotNone(model_view[k_distance])  # Distance should be calculated
        self.assertEqual(model_view[k_no_travel_cost], True)
        self.assertEqual(model_view[k_note], 'Test note without distance')

    def test_distance_calculation(self):
        # Verify that the distance is calculated automatically when not provided
        self.assertIsNotNone(self.job_application_without_distance.distance)
        self.assertGreater(self.job_application_without_distance.distance, 0)

        # Verify that the distance matches the expected value (calculated using GeoUtil)
        expected_distance = GeoUtil.get_distance(
            self.job.address.latitude, self.job.address.longitude,
            self.job_application_without_distance.address.latitude,
            self.job_application_without_distance.address.longitude
        )
        self.assertEqual(self.job_application_without_distance.distance, expected_distance)


class TimeRegistrationModelTest(TestCase):

    def setUp(self):
        self.address = Address.objects.create(
            street_name='123 Main St',
            city='Anytown',
            zip_code='12345',
            country='USA'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password'
        )
        self.job = Job.objects.create(
            customer=self.user,
            title='Test Job',
            description='This is a test job.',
            address=self.address,
            job_state='pending',
            start_time=timezone.now() + datetime.timedelta(days=1),
            end_time=timezone.now() + datetime.timedelta(days=2),
            application_start_time=timezone.now() - datetime.timedelta(days=1),
            application_end_time=timezone.now() + datetime.timedelta(days=1),
            is_draft=False,
            archived=False,
            max_workers=10,
            selected_workers=5
        )
        self.time_registration = TimeRegistration.objects.create(
            job=self.job,
            worker=self.user,
            start_time=timezone.now(),
            end_time=timezone.now() + datetime.timedelta(hours=8),
            break_time=datetime.time(hour=1)
        )

    def test_to_model_view(self):
        model_view = self.time_registration.to_model_view()
        self.assertEqual(model_view[k_id], self.time_registration.id)
        self.assertEqual(model_view[k_start_time], FormattingUtil.to_timestamp(self.time_registration.start_time))
        self.assertEqual(model_view[k_end_time], FormattingUtil.to_timestamp(self.time_registration.end_time))
        self.assertEqual(model_view[k_break_time], FormattingUtil.to_timestamp(self.time_registration.break_time))
        self.assertEqual(model_view[k_worker][k_id], self.user.id)
