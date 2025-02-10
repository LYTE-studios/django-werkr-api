import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.authentication.models.profiles.customer_profile import CustomerProfile
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.authentication.managers.user_manager import UserManager

User = get_user_model()


class UserManagerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="password123"
        )
        self.address = Address.objects.create(
            street="123 Test St",
            city="Test City",
            state="Test State",
            zip_code="12345",
            country="Test Country",
        )

    def test_create_user(self):
        user = UserManager.create_user(self.user)
        self.assertIsNotNone(user.settings)
        self.assertEqual(user.email, "testuser@example.com")

    def test_create_worker_profile(self):
        UserManager.create_worker_profile(
            user=self.user,
            iban="DE89370400440532013000",
            ssn="123-45-6789",
            worker_address=self.address,
            date_of_birth=datetime.date(1990, 1, 1),
            place_of_birth="Test City",
        )
        worker_profile = WorkerProfile.objects.get(user=self.user)
        self.assertEqual(worker_profile.iban, "DE89370400440532013000")
        self.assertEqual(worker_profile.ssn, "123-45-6789")
        self.assertEqual(worker_profile.worker_address, self.address)
        self.assertEqual(worker_profile.date_of_birth, datetime.date(1990, 1, 1))
        self.assertEqual(worker_profile.place_of_birth, "Test City")

    def test_create_customer_profile(self):
        UserManager.create_customer_profile(
            user=self.user,
            tax_number="123456789",
            company_name="Test Company",
            customer_address=self.address,
            customer_billing_address=self.address,
        )
        customer_profile = CustomerProfile.objects.get(user=self.user)
        self.assertEqual(customer_profile.tax_number, "123456789")
        self.assertEqual(customer_profile.company_name, "Test Company")
        self.assertEqual(customer_profile.customer_address, self.address)
        self.assertEqual(customer_profile.customer_billing_address, self.address)
