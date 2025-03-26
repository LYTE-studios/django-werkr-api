from django.test import TestCase
from apps.authentication.models.user import User
from apps.core.models.settings import Settings
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.authentication.models.profiles.admin_profile import AdminProfile
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.authentication.models.profiles.customer_profile import CustomerProfile
from apps.core.models.geo import Address

User = get_user_model()


class UserModelTest(TestCase):

    def setUp(self):
        self.settings = Settings.objects.create(language='en')
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User',
            fcm_token='sample_token',
            salt='sample_salt',
            description='Sample description',
            phone_number='1234567890',
            settings=self.settings,
            archived=False
        )

    def test_user_creation(self):
        self.assertIsNotNone(self.user)
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'testuser@example.com')
        self.assertEqual(self.user.first_name, 'Test')
        self.assertEqual(self.user.last_name, 'User')
        self.assertEqual(self.user.fcm_token, 'sample_token')
        self.assertEqual(self.user.salt, 'sample_salt')
        self.assertEqual(self.user.description, 'Sample description')
        self.assertEqual(self.user.phone_number, '1234567890')
        self.assertEqual(self.user.settings, self.settings)
        self.assertFalse(self.user.archived)


class AdminProfileModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='adminuser',
            email='adminuser@example.com',
            password='password123'
        )
        self.admin_profile = AdminProfile.objects.create(user=self.user, session_duration=30)

    def test_admin_profile_creation(self):
        self.assertIsNotNone(self.admin_profile)
        self.assertEqual(self.admin_profile.user, self.user)
        self.assertEqual(self.admin_profile.session_duration, 30)


class CustomerProfileModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='customeruser',
            email='customeruser@example.com',
            password='password123'
        )
        self.address = Address.objects.create()
        self.customer_profile = CustomerProfile.objects.create(
            user=self.user,
            tax_number='123456789',
            company_name='Sample Company',
            customer_billing_address=self.address,
            customer_address=self.address,
            special_committee='Sample Committee'
        )

    def test_customer_profile_creation(self):
        self.assertIsNotNone(self.customer_profile)
        self.assertEqual(self.customer_profile.user, self.user)
        self.assertEqual(self.customer_profile.tax_number, '123456789')
        self.assertEqual(self.customer_profile.company_name, 'Sample Company')
        self.assertEqual(self.customer_profile.customer_billing_address, self.address)
        self.assertEqual(self.customer_profile.customer_address, self.address)
        self.assertEqual(self.customer_profile.special_committee, 'Sample Committee')


class WorkerProfileModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='workeruser',
            email='workeruser@example.com',
            password='password123'
        )
        self.address = Address.objects.create()
        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
            iban='DE89370400440532013000',
            ssn='123-45-6789',
            worker_address=self.address,
            date_of_birth='1990-01-01',
            place_of_birth='Sample City',
            accepted=True,
            hours=40.0,
            worker_type=WorkerProfile.WorkerType.STUDENT,
            has_passed_onboarding=False
        )

    def test_worker_profile_creation(self):
        self.assertIsNotNone(self.worker_profile)
        self.assertEqual(self.worker_profile.user, self.user)
        self.assertEqual(self.worker_profile.iban, 'DE89370400440532013000')
        self.assertEqual(self.worker_profile.ssn, '123-45-6789')
        self.assertEqual(self.worker_profile.worker_address, self.address)
        self.assertEqual(self.worker_profile.date_of_birth, '1990-01-01')
        self.assertEqual(self.worker_profile.place_of_birth, 'Sample City')
        self.assertTrue(self.worker_profile.accepted)
        self.assertEqual(self.worker_profile.hours, 40.0)
        self.assertEqual(self.worker_profile.worker_type, WorkerProfile.WorkerType.STUDENT)
        self.assertFalse(self.worker_profile.has_passed_onboarding)
