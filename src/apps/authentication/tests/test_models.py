from apps.authentication.models.pass_reset import PassResetCode
from apps.core.models.settings import Settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()

from apps.core.models.geo import Address
from apps.authentication.models.profiles.admin_profile import AdminProfile
from apps.authentication.models.profiles.customer_profile import CustomerProfile
from apps.authentication.models.profiles.worker_profile import WorkerProfile


class UserModelTest(TestCase):

    def setUp(self):
        self.settings = Settings.objects.create(language='en')
        self.user = get_user_model().objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            password='password123',
            settings=self.settings,
            fcm_token='sample_token',
            description='Sample description',
            profile_picture=None,
            archived=False,
            accepted=True,
            hours=40.0,
            session_duration=30,
            place_of_birth='Sample City'
        )

    def test_user_creation(self):
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'john.doe@example.com')
        self.assertEqual(self.user.settings, self.settings)
        self.assertEqual(self.user.fcm_token, 'sample_token')
        self.assertEqual(self.user.description, 'Sample description')
        self.assertFalse(self.user.archived)
        self.assertTrue(self.user.accepted)
        self.assertEqual(self.user.hours, 40.0)
        self.assertEqual(self.user.session_duration, 30)
        self.assertEqual(self.user.place_of_birth, 'Sample City')

    def test_user_string_representation(self):
        self.assertEqual(str(self.user), self.user.username)

    def test_user_profile_picture_upload_path(self):
        self.assertIsNone(self.user.profile_picture)


class PassResetCodeModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123'
        )
        self.pass_reset_code = PassResetCode.objects.create(
            user=self.user,
            code='123456',
            reset_password_token='sample_token',
            token_expiry_time=timezone.now() + timezone.timedelta(hours=1)
        )

    def test_pass_reset_code_creation(self):
        self.assertEqual(self.pass_reset_code.user, self.user)
        self.assertEqual(self.pass_reset_code.code, '123456')
        self.assertFalse(self.pass_reset_code.used)
        self.assertEqual(self.pass_reset_code.reset_password_token, 'sample_token')
        self.assertIsNotNone(self.pass_reset_code.token_expiry_time)

    def test_pass_reset_code_string_representation(self):
        self.assertEqual(str(self.pass_reset_code), self.pass_reset_code.code)


class ProfileModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123'
        )
        self.address = Address.objects.create(
            street_name='123 Main St',
            city='Sample City',
            zip_code='12345',
            country='Sample Country'
        )

    def test_admin_profile_creation(self):
        admin_profile = AdminProfile.objects.create(
            user=self.user,
            session_duration=30
        )
        self.assertEqual(admin_profile.user, self.user)
        self.assertEqual(admin_profile.session_duration, 30)

    def test_customer_profile_creation(self):
        customer_profile = CustomerProfile.objects.create(
            user=self.user,
            phone_number='1234567890',
            tax_number='TAX123456',
            company_name='Sample Company',
            customer_billing_address=self.address,
            customer_address=self.address
        )
        self.assertEqual(customer_profile.user, self.user)
        self.assertEqual(customer_profile.phone_number, '1234567890')
        self.assertEqual(customer_profile.tax_number, 'TAX123456')
        self.assertEqual(customer_profile.company_name, 'Sample Company')
        self.assertEqual(customer_profile.customer_billing_address, self.address)
        self.assertEqual(customer_profile.customer_address, self.address)

    def test_worker_profile_creation(self):
        worker_profile = WorkerProfile.objects.create(
            user=self.user,
            iban='IBAN123456',
            ssn='SSN123456',
            worker_address=self.address,
            date_of_birth='1990-01-01',
            place_of_birth='Sample City',
            accepted=True,
            hours=40.0
        )
        self.assertEqual(worker_profile.user, self.user)
        self.assertEqual(worker_profile.iban, 'IBAN123456')
        self.assertEqual(worker_profile.ssn, 'SSN123456')
        self.assertEqual(worker_profile.worker_address, self.address)
        self.assertEqual(worker_profile.date_of_birth, '1990-01-01')
        self.assertEqual(worker_profile.place_of_birth, 'Sample City')
        self.assertTrue(worker_profile.accepted)
        self.assertEqual(worker_profile.hours, 40.0)
