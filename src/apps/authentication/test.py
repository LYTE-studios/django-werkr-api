# from ..unit_tests.test_views import *
# from ..unit_tests.test_models import *


from django.utils import timezone
from django.urls import reverse
from django.test import RequestFactory
import datetime
import tempfile
from unittest.mock import patch
from uuid import UUID

from apps.authentication.models import CustomerProfile, WorkerProfile, AdminProfile
from apps.authentication.utils.authentication_util import AuthenticationUtil
from apps.authentication.utils.jwt_auth_util import JWTAuthUtil
from apps.authentication.views import BaseClientView, ProfileCompletionView
from apps.authentication.views import JWTBaseAuthView
from apps.core.assumptions import CMS_GROUP_NAME, CUSTOMERS_GROUP_NAME
from apps.core.assumptions import WORKERS_GROUP_NAME
from apps.core.model_exceptions import DeserializationException
from apps.core.models.settings import Settings
from apps.core.utils.wire_names import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseForbidden
from django.test import RequestFactory
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework import status
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.authentication.models.dashboard_flow import DashboardFlow
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.authtoken.models import Token
from apps.core.models.geo import Address
User = get_user_model()
from apps.authentication.utils.worker_util import WorkerUtil
from apps.authentication.utils.customer_util import CustomerUtil
from apps.jobs.models import Job, JobState, JobApplication



class ProfileCompletionViewTest(APITestCase):

    def setUp(self):
        # Create User and WorkerProfile for user1 (incomplete profile)
        self.user1, created = User.objects.update_or_create(
            username="testuser1", 
            defaults={
                "email": "worker1@e", 
                "password": "helllo)there"
            }
        )

        self.worker_profile_incomplete = WorkerProfile.objects.create(
            user=self.user1,
            iban="",  # Missing IBAN
            ssn="123-45-6789",
            worker_type="freelancer"
        )

        # Create User and WorkerProfile for user2 (complete profile)
        self.user2, created = User.objects.update_or_create(
            username="testuser2", 
            defaults={
                "email": "worker2@e", 
                "password": "password123"
            }
        )

        # Create a job and job application for the worker
        address = Address.objects.create(
            street_name="123 Main St",
            house_number="45A",
            box_number="",
            city="Some City",
            zip_code="12345",
            country="Country Name",
            latitude=52.5200,
            longitude=13.4050
        )

        self.worker_profile_complete = WorkerProfile.objects.create(
            user=self.user2,
            iban="DE89370400440532013000",
            ssn="123-45-6789",
            worker_type="freelancer",
            date_of_birth=datetime.datetime.now(),
            place_of_birth="Candyland",
            worker_address=address
        )

        
        # Create a customer (who will be the customer for the job)
        self.customer, created = User.objects.update_or_create(
            username="customer", 
            defaults={
                "email": "example@example.com",
                "password": "password123"
            }
        )
        
        self.job = Job.objects.create(title="New job", address=address, customer=self.customer)
        
        # Create job application for user2 (worker)
        self.job_application_complete = JobApplication.objects.create(
            worker=self.user2,
            job=self.job,
            address=address,
            application_state="pending",
            created_at=timezone.now(),
            modified_at=timezone.now(),
        )


    def test_worker_profile_completion_complete(self):
        """
        Test case for checking a worker profile that is 100% complete.
        """

        self.client.force_login(self.user2)

        # Send a GET request to the profile completion endpoint for the complete worker (user2)
        response = self.client.get(reverse('profile_completion'))
    
        # Assert that the response status code is HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        print(response.json())
    
        # Assert that the response contains the correct completion percentage and missing fields
        self.assertEqual(response.data['completion_percentage'], 100)
        self.assertEqual(response.data['missing_fields'], [])

    def test_worker_profile_completion_incomplete(self):
        """
        Test case for checking a worker profile that is incomplete.
        """
        self.client.force_login(self.user1)

        # Send a GET request to the profile completion endpoint for the incomplete worker (user1)
        response = self.client.get(reverse('profile_completion'))

        # Assert that the response status code is HTTP 400 Bad Request (due to incomplete profile)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
        # Assert that the response contains the correct error message
        # self.assertIn("Profile is incomplete", str(response.data))
        self.assertIn("iban", str(response.data))  # Check the missing field is listed
      
        