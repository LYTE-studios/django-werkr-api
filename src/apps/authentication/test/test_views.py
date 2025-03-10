import json
from uuid import UUID
from django.test import RequestFactory
import datetime
import tempfile
from unittest.mock import patch
from django.conf import settings

from apps.authentication.models import CustomerProfile, WorkerProfile, AdminProfile
from apps.authentication.utils.authentication_util import AuthenticationUtil
from apps.authentication.utils.jwt_auth_util import JWTAuthUtil
from apps.authentication.views import BaseClientView, PasswordResetRequestView, ProfileCompletionView
from apps.authentication.views import JWTBaseAuthView
from apps.core.assumptions import CMS_GROUP_NAME, CUSTOMERS_GROUP_NAME
from apps.core.assumptions import WORKERS_GROUP_NAME
from apps.core.model_exceptions import DeserializationException
from apps.core.models.settings import Settings
from apps.core.utils.wire_names import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse, HttpResponseForbidden
from django.test import RequestFactory
from django.test import TestCase, Client
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.authentication.models.dashboard_flow import DashboardFlow
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models.geo import Address
from apps.authentication.utils.encryption_util import EncryptionUtil
from apps.authentication.models.custom_group import CustomGroup
from apps.core.utils.formatters import FormattingUtil
User = get_user_model()
from apps.authentication.utils.worker_util import WorkerUtil
from apps.authentication.utils.customer_util import CustomerUtil
from apps.jobs.models import Job, JobState, JobApplication



class BaseClientViewTest(TestCase):

    def setUp(self):
        print("Running BaseClientViewTest setup")
        self.factory = RequestFactory()
        self.view = BaseClientView.as_view()
        self.client = APIClient()
        try: 
            self.group = Group.objects.get(name=WORKERS_GROUP_NAME)
        except Group.DoesNotExist:
            self.group, created = Group.objects.get_or_create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(username="testuser", email="testuser@example.com", password="testpassword")
        self.user.groups.add(self.group)
        

    def test_options_request(self):
        self.client.force_login(self.user)
        request = self.factory.options('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('allow', response)

    def test_dispatch_with_valid_group(self):
        request = self.factory.options('/')
        request.META['HTTP_CLIENT_SECRET'] = 'valid_secret'
        self.group.refresh_from_db()
        with self.settings(AUTHENTICATION_UTIL=AuthenticationUtil):
            AuthenticationUtil.check_client_secret = lambda req: self.group
            response = self.view(request)
            self.assertEqual(response.status_code, 200)

    def test_dispatch_with_invalid_group(self):
        request = self.factory.get('/')
        request.META['HTTP_CLIENT_SECRET'] = 'invalid_secret'
        self.group.refresh_from_db()
        with self.settings(AUTHENTICATION_UTIL=AuthenticationUtil):
            AuthenticationUtil.check_client_secret = lambda req: None
            response = self.view(request)
            self.assertEqual(response.status_code, 403)


class JWTBaseAuthViewTestOld(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = JWTBaseAuthView.as_view()
        self.client = APIClient()
        self.group = Group.objects.create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='password123', email='test@example.com')
        self.user.groups.add(self.group)
        self.token = AccessToken.for_user(self.user)

    def test_dispatch_with_valid_token(self):
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {self.token}'
        request.META['HTTP_CLIENT_SECRET'] = 'valid_secret'
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.check_for_authentication = lambda req: self.token
            response = self.view(request)
            self.assertEqual(response.status_code, 200)

    def test_dispatch_with_invalid_token(self):
        request = self.factory.get('/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer invalid_token'
        request.META['HTTP_CLIENT_SECRET'] = 'valid_secret'
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.check_for_authentication = lambda req: None
            response = self.view(request)
            self.assertEqual(response.status_code, 403)


class JWTAuthenticationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('token_obtain_pair')
        self.valid_payload = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        self.invalid_payload = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }

    def test_post_with_valid_credentials(self):
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.authenticate = lambda email, password, group: {'access': 'access_token', 'refresh': 'refresh_token'}
            response = self.client.post(self.url, self.valid_payload, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('access', response.data)
            self.assertIn('refresh', response.data)

    def test_post_with_invalid_credentials(self):
        with self.settings(JWT_AUTH_UTIL=JWTAuthUtil):
            JWTAuthUtil.authenticate = lambda email, password, group: {}
            response = self.client.post(self.url, self.invalid_payload, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data['message'], 'Invalid credentials')
            print(response.data)


class ProfileMeViewTestOld(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.group = Group.objects.create(name='test_group')
        self.settings = Settings.objects.create(language='en')
        self.user = User.objects.create_user(
            username='testuser',
            password='password123',
            email='testuser@example.com',
            first_name='Test',
            last_name='User',
            description='Sample description',
            settings=self.settings
        )
        self.user.groups.add(self.group)
        self.client.force_authenticate(user=self.user)

    @patch('apps.authentication.utils.profile_util.ProfileUtil.get_user_profile_picture_url', return_value='profile_pic_url')
    def test_get_profile(self, mock_get_user_profile_picture_url):
        url = reverse('profile_me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_id'], str(self.user.id))
        self.assertEqual(response.data['first_name'], 'Test')
        self.assertEqual(response.data['last_name'], 'User')
        self.assertEqual(response.data['email'], 'testuser@example.com')
        self.assertEqual(response.data['description'], 'Sample description')
        self.assertEqual(response.data['profile_picture'], 'profile_pic_url')
        self.assertEqual(response.data['language'], 'en')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=lambda key: 'new_value')
    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='new_email@example.com')
    def test_put_profile(self, mock_get_email, mock_get_value):
        url = reverse('profile_me')
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'new_email@example.com',
            'description': 'New description'
        }
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'new_email@example.com')
        self.assertEqual(self.user.description, 'New description')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_put_profile_invalid_data(self, mock_get_value):
        url = reverse('profile_me')
        data = {'first_name': 'John'}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], ('Invalid data',))

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_put_profile_server_error(self, mock_get_value):
        url = reverse('profile_me')
        data = {'first_name': 'John'}
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['message'], ('Server error',))


class LanguageSettingsViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.client.login(username='testuser', password='12345')

    @patch('apps.core.models.settings.Settings.objects.all')
    def test_get_languages(self, mock_settings_all):
        mock_settings_all.return_value = [
            Settings(language='en'),
            Settings(language='fr'),
            Settings(language='en')
        ]
        response = self.client.get(reverse('language_settings'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'languages': ['en', 'fr']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', return_value='es')
    @patch('apps.core.models.settings.Settings.objects.create')
    def test_put_language(self, mock_settings_create, mock_get_value):
        settings = Settings(language='en')
        settings.save()
        self.user.settings = settings
        self.user.save()
        mock_settings_create.return_value = settings

        data = {'language': 'es'}
        response = self.client.put(reverse('language_settings'), data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.settings.language, 'es')
        self.assertEqual(response.json(), {'language': 'es'})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_put_language_invalid_data(self, mock_get_value):
        data = {'language': 'invalid'}
        response = self.client.put(reverse('language_settings'), data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_put_language_server_error(self, mock_get_value):
        data = {'language': 'es'}
        response = self.client.put(reverse('language_settings'), data, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {'message': ['Server error']})


class UploadUserProfilePictureViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.client.login(username='testuser', password='12345')

    def test_get_profile_picture(self):
        response = self.client.get(reverse('upload_profile_picture', kwargs={'id': self.user.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['profile_picture'])

    def test_put_profile_picture(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
            temp_file.write(b"file_content")
            temp_file.seek(0)
            uploaded_file = SimpleUploadedFile(name="test.jpg", content=temp_file.read(), content_type="image/jpeg")
            print(f"Uploaded file content type: {uploaded_file.content_type}")
            

            response = self.client.put(reverse('upload_profile_picture', kwargs={'id': self.user.id}),
                                       {'file': uploaded_file}, format='multipart')
            print(f"response data: {response.data}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.user.refresh_from_db()
            self.assertTrue(self.user.profile_picture.name.endswith(".jpg"))


class PasswordResetRequestViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse("password_reset")
        self.client.force_login(self.user)

    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.send_reset_code', return_value=True)
    def test_post_valid_email(self, mock_send_reset_code):
        """Test the password reset request with a valid email"""
        self.client.force_login(self.user)
        data = {'email': 'test@example.com'}
        response = self.client.post(self.url, data=json.dumps(data), content_type="application/json", headers={"Client": settings.WORKER_GROUP_SECRET})
        print("Response Status Code:", response.status_code)
        print("Response Content:", response.content.decode("utf-8"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'message': 'Password reset email has been sent.'})

    @patch('apps.core.utils.formatters.FormattingUtil.get_email', side_effect=Exception('Invalid email'))
    def test_post_invalid_email(self, mock_get_email):
        data = {'email': 'invalid'}
        response = self.client.post(reverse('password_reset'), data, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='notfound@example.com')
    def test_post_email_not_found(self, mock_get_email):
        data = {'email': 'notfound@example.com'}
        response = self.client.post(reverse('password_reset'), data, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {'message': 'Email not found.'})


class VerifyCodeViewTest(APITestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username='testuser', password='12345', email='test@example.com')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'test@example.com' if key == 'email' else '123456')
    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.verify_code', return_value=True)
    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.create_temporary_token_for_user',
           return_value='temporary_token')
    def test_post_valid_code(self, mock_create_token, mock_verify_code, mock_get_value):
        data = {'email': 'test@example.com', 'code': '123456'}
        response = self.client.post(reverse('password_reset_verify'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'token': 'temporary_token'})
        mock_verify_code.assert_called_once_with(self.user, '123456')
        mock_create_token.assert_called_once_with(self.user, '123456')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'test@example.com' if key == 'email' else 'wrong_code')
    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.verify_code', return_value=False)
    def test_post_invalid_code(self, mock_verify_code, mock_get_value):
        data = {'email': 'test@example.com', 'code': 'wrong_code'}
        response = self.client.post(reverse('password_reset_verify'), data, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
        print(response.status_code)  # Debugging
        print(response.json()) 
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json(), {'message': 'Code not verified.'})
        mock_verify_code.assert_called_once_with(self.user, 'wrong_code')
        response.content.decode()

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Invalid data'))
    def test_post_invalid_data(self, mock_get_value):
        data = {'email': 'invalid'}
        response = self.client.post(reverse('password_reset_verify'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'notfound@example.com' if key == 'email' else '123456')
    def test_post_email_not_found(self, mock_get_value):
        data = {'email': 'notfound@example.com', 'code': '123456'}
        response = self.client.post(reverse('password_reset_verify'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': 'Email not found.'})


class ResetPasswordViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=lambda key, required=False: 'valid_token' if key == 'token' else '123456' if key == 'code' else 'new_password')
    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.get_user_by_token_and_code', return_value=None)
    @patch('apps.authentication.utils.encryption_util.EncryptionUtil.encrypt', return_value=('encrypted_password', 'salt_value'))
    def test_post_valid_data(self, mock_encrypt, mock_get_user, mock_get_value):
        mock_get_user.return_value = self.user
        data = {'token': 'valid_token', 'code': '123456', 'password': 'new_password'}
        response = self.client.post(reverse('password_reset_reset'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'message': 'Password has been reset.'})
        mock_get_user.assert_called_once_with('valid_token', '123456')
        mock_encrypt.assert_called_once_with('new_password')
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, 'encrypted_password')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=lambda key,
                                                                                     required=False: 'invalid_token' if key == 'token' else '123456' if key == 'code' else 'new_password')
    @patch('apps.authentication.utils.pass_reset_util.CustomPasswordResetUtil.get_user_by_token_and_code',
           return_value=None)
    def test_post_invalid_token(self, mock_get_user, mock_get_value):
        data = {'token': 'invalid_token', 'code': '123456', 'password': 'new_password'}
        response = self.client.post(reverse('password_reset_reset'), data, content_type='application/json',headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': 'Invalid or expired token'})
        mock_get_user.assert_called_once_with('invalid_token', '123456')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Invalid data'))
    def test_post_invalid_data(self, mock_get_value):
        data = {'token': 'invalid'}
        response = self.client.post(reverse('password_reset_reset'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': ['Invalid data']})



class WorkerRegisterViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group = Group.objects.get_or_create(name=WORKERS_GROUP_NAME)

    @patch('apps.core.utils.formatters.FormattingUtil.get_address', return_value=None)
    @patch('apps.authentication.utils.encryption_util.EncryptionUtil.encrypt', return_value=('encrypted_password', 'salt_value'))
    @patch('apps.authentication.managers.user_manager.UserManager.create_user', return_value= User(username='testuser',email='test@example.com', password='password123'))
    @patch('apps.authentication.managers.user_manager.UserManager.create_worker_profile')
    def test_post_valid_data(self, mock_create_worker_profile, mock_create_user, mock_encrypt, mock_get_address,
                             ):
        mock_create_user.return_value = User.objects.create_user(
           username='testuser', email='test@example.com', password='password123'
        )
        # Send a request to register a worker with the same email
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'test2@example.com',
            'password': 'password123',
            'phone_number': '1234567890',
            'date_of_birth': 000000,
            'iban': 'DE89370400440532013000',
            'place_of_birth': 'City',
            'ssn': '123-45-6789',
            'worker_address': None,
            'work_types': [{'id': 1}, {'id': 2}],
            'situation_types': [{'id': 1}],
            'job_types': [{'id': 1, 'mastery': 'beginner'}],
            'locations': [{'id': 1}]
        }


        response = self.client.post(reverse('worker_register'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        print(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        mock_create_user.assert_called_once()
        mock_create_worker_profile.assert_called_once()

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_post_invalid_data(self, mock_get_value):
        data = {'first_name': 'John'}
        response = self.client.post(reverse('worker_register'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='test@example.com')
    def test_post_user_already_exists(self, mock_get_email):
        User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        data = {'email': 'test@example.com'}
        response = self.client.post(reverse('worker_register'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_post_server_error(self, mock_get_value):
        data = {'first_name': 'John'}
        response = self.client.post(reverse('worker_register'), data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {'message': ['Server error']})


class StatisticsViewTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username="testuser", email="testuser@example.com")
        self.group = Group.objects.get(name=WORKERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        self.client = Client()
        self.url = reverse('statistics_view')
        self.valid_data = {
            k_worker_id: 'worker_id',
            k_time_frame: k_week
        }
        self.client.force_login(self.user)
    

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'worker_id' if key == k_worker_id else k_week)
    @patch('apps.jobs.services.statistics_service.StatisticsService.get_weekly_stats',
           return_value={'week_stats': 'data'})
    def test_post_valid_weekly_data(self, mock_get_weekly_stats, mock_get_value):
        response = self.client.post(self.url, self.valid_data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(),
                         {k_statistics: [{'week_stats': 'data'}, {'week_stats': 'data'}, {'week_stats': 'data'}]})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'worker_id' if key == k_worker_id else k_month)
    @patch('apps.jobs.services.statistics_service.StatisticsService.get_monthly_stats',
           return_value={'year_stats': 'data'})
    def test_post_valid_monthly_data(self, mock_get_monthly_stats, mock_get_value):
        response = self.client.post(self.url, {k_worker_id: 'worker_id', k_time_frame: k_month},
                                    content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(),
                         {k_statistics: [{'year_stats': 'data'}, {'year_stats': 'data'}, {'year_stats': 'data'}]})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_post_invalid_data(self, mock_get_value):
        response = self.client.post(self.url, {}, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value',
           side_effect=lambda key, required=False: 'worker_id' if key == k_worker_id else 'invalid_time_frame')
    def test_post_invalid_time_frame(self, mock_get_value):
        response = self.client.post(self.url, {k_worker_id: 'worker_id', k_time_frame: 'invalid_time_frame'},
                                    content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: 'Invalid time frame'})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_post_server_error(self, mock_get_value):
        response = self.client.post(self.url, self.valid_data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ['Server error']})


class WorkerDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        from apps.authentication.models import WorkerProfile
        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
        )
        self.user.save()
        self.url = reverse('worker_detail', kwargs={'id': self.user.id})
        self.client.force_login(self.user)

    def test_get_valid_worker(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_response = WorkerUtil.to_worker_view(self.user)
    
        # Convert UUID to string and Enum to its value
        expected_response["id"] = str(expected_response["id"])  
        expected_response["worker_type"] = expected_response["worker_type"].value  

        self.assertEqual(response.json(), expected_response)


    def test_get_invalid_worker(self):
        url = reverse('worker_detail', kwargs={'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_valid_worker(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.groups.filter(name=WORKERS_GROUP_NAME).exists())

    def test_delete_invalid_worker(self):
        url = reverse('worker_detail', kwargs={'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def mock_get_value_side_effect(*args, **kwargs):
        if args[0] == k_first_name:
            return "John"
        elif args[0] == k_last_name:
            return "Doe"
        return None  # Default case

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=mock_get_value_side_effect)
    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='new_email@example.com')
    @patch('apps.core.utils.formatters.FormattingUtil.get_address', return_value=None)
    @patch('apps.core.utils.formatters.FormattingUtil.get_date', return_value='2000-01-01')
    def test_put_valid_worker(self, mock_get_date, mock_get_address, mock_get_email, mock_get_value):
        data = {
            k_first_name: 'John',
            k_last_name: 'Doe',
            k_phone_number: '1234567890',
            k_email: 'new_email@example.com',
            k_address: None,
            k_date_of_birth: '2000-01-01',
            k_billing_address: None,
            k_tax_number: '123456789',
            k_company: 'New Company'
        }
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'new_email@example.com')
        

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_put_invalid_data(self, mock_get_value):
        data = {k_first_name: 'John'}
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_put_server_error(self, mock_get_value):
        data = {k_first_name: 'John'}
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ['Server error']})


class WorkersListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse('workers_list')
        self.client.force_login(self.user)

    @patch('apps.authentication.utils.worker_util.WorkerUtil.to_worker_view',
           side_effect=lambda worker: {'id': worker.id, 'email': worker.email})
    def test_get_workers_list(self, mock_to_worker_view):
        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.worker_util.WorkerUtil.to_worker_view',
           side_effect=lambda worker: {'id': worker.id, 'email': worker.email})
    def test_get_workers_list_with_search_term(self, mock_to_worker_view):
        response = self.client.get(self.url, {'search_term': 'test'}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.worker_util.WorkerUtil.to_worker_view',
           side_effect=lambda worker: {'id': worker.id, 'email': worker.email})
    def test_get_workers_list_with_sort_term(self, mock_to_worker_view):
        response = self.client.get(self.url, {'sort_term': 'email', 'algorithm': 'descending'}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.worker_util.WorkerUtil.to_worker_view',
           side_effect=lambda worker: {'id': worker.id, 'email': worker.email})
    def test_get_workers_list_with_pagination(self, mock_to_worker_view):
        response = self.client.get(self.url, {'count': 10, 'page': 2}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.worker_util.WorkerUtil.to_worker_view',
           side_effect=lambda worker: {'id': worker.id, 'email': worker.email})
    def test_get_workers_list_with_state(self, mock_to_worker_view):
        response = self.client.get(self.url, {'state': 'registered'}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_workers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())


class AcceptWorkerViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=WORKERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        from apps.authentication.models import WorkerProfile
        self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
        )
        self.user.save()
        self.url = reverse('accept_worker', kwargs={'id': self.user.id})
        self.client.force_login(self.user)

    def test_post_valid_worker(self):
        response = self.client.post(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.worker_profile.accepted)

    def test_post_invalid_worker(self):
        url = reverse('accept_worker', kwargs={'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'})
        response = self.client.post(url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CreateCustomerViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=CMS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        self.url = reverse('create_customer')
        self.client.force_login(self.user)

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=lambda key, required=False: 'test_value')
    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='test@example.com')
    @patch('apps.core.utils.formatters.FormattingUtil.get_address', return_value=None)
    @patch('apps.authentication.managers.user_manager.UserManager.create_customer_profile')
    def test_post_valid_data(self, mock_create_customer_profile, mock_get_address, mock_get_email, mock_get_value):
        data = {
            k_first_name: 'John',
            k_last_name: 'Doe',
            k_email: 'test@example.com',
            k_address: None,
            k_billing_address: None,
            k_tax_number: '123456789',
            k_company: 'Test Company',
            k_phone_number: '1234567890'
        }
        response = self.client.post(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        self.assertEqual(response.json(), {k_customer_id: str(user.id)})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_post_invalid_data(self, mock_get_value):
        data = {k_first_name: 'John'}
        response = self.client.post(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {k_message: ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=lambda key, required=False: 'test_value')
    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='test@example.com')
    @patch('apps.core.utils.formatters.FormattingUtil.get_address', return_value=None)
    def test_post_user_already_exists(self, mock_get_address, mock_get_email, mock_get_value):
        
        # Ensure no user exists before running the test
        User.objects.filter(email='test@example.com').delete()

        # Create a user and force login
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.client.force_login(self.user)
        data = {
            k_first_name: 'John',
            k_last_name: 'Doe',
            k_email: 'test@example.com',
            k_address: None,
            k_billing_address: None,
            k_tax_number: '123456789',
            k_company: 'Test Company',
            k_phone_number: '1234567890'
        }
        
        # Make sure the user exists before making the POST request
        user_exists = User.objects.filter(email='test@example.com').exists()
        self.assertTrue(user_exists, "User should be created successfully")

        data = {'email': 'test@example.com'}
        response = self.client.post(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        
        # Check the response status and ensure the user still exists
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())


    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_post_server_error(self, mock_get_value):
        data = {k_first_name: 'John'}
        response = self.client.post(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {k_message: ['Server error']})


class CustomersListViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse('customers_list')
        self.client.force_login(self.user)

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer, has_active_job: {'id': customer.id, 'email': customer.email})
    def test_get_customers_list(self, mock_to_customer_view):
        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer, has_active_job: {'id': customer.id, 'email': customer.email})
    def test_get_customers_list_with_search_term(self, mock_to_customer_view):
        response = self.client.get(self.url, {'search_term': 'test'}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer, has_active_job: {'id': customer.id, 'email': customer.email})
    def test_get_customers_list_with_sort_term(self, mock_to_customer_view):
        response = self.client.get(self.url, {'sort_term': 'email', 'algorithm': 'descending'}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer, has_active_job: {'id': customer.id, 'email': customer.email})
    def test_get_customers_list_with_pagination(self, mock_to_customer_view):
        response = self.client.get(self.url, {'count': 10, 'page': 2}, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer, has_active_job: {'id': customer.id, 'email': customer.email})
    def test_get_customers_list_with_active_job(self, mock_to_customer_view):
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
        start_time = timezone.make_aware(datetime.datetime.utcnow())
        end_time = timezone.make_aware(datetime.datetime.utcnow())
       
        job = Job.objects.create(customer=self.user, start_time=start_time,
                                 end_time=end_time, job_state=JobState.pending, address=address)
        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())
        self.assertIn(k_items_per_page, response.json())
        self.assertIn(k_total, response.json())
        job.delete()


class CustomerDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        from apps.authentication.models import CustomerProfile
        self.customer_profile = CustomerProfile.objects.create(
            user=self.user,
        )
    
        self.user.save()
        self.url = reverse('worker_detail', kwargs={'id': self.user.id})
        self.client.force_login(self.user)
        self.user.save()
        self.url = reverse('customer_detail', kwargs={'id': self.user.id})
        self.client.force_login(self.user)

    def test_get_valid_customer(self):
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
        billing_address = Address.objects.create(
            street_name="123 Main St",
            house_number="45A",
            box_number="",
            city="Some City",
            zip_code="12345",
            country="Country Name",
            latitude=52.5200,
            longitude=13.4050
        )    
        self.customer_profile.customer_address = address
        self.customer_profile.customer_billing_address = billing_address
        self.customer_profile.save()        
        expected_data = {
            "id": str(self.user.id),  
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "email": self.user.email,
            "created_at": FormattingUtil.to_timestamp(self.user.date_joined),
            "address": address.to_model_view(), 
            "billing_address": billing_address.to_model_view(), 
            "tax_number": self.customer_profile.tax_number,  # Ensure this is not None or set to None in the test
            "company": self.customer_profile.company_name,  # Same for company
            "has_active_job": False,  # Adjust if you need to reflect an active job status
            "phone_number": self.user.phone_number,
            "special_committee": self.customer_profile.special_committee,
            "profile_picture":None,
            }

        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), expected_data)

    def test_get_invalid_customer(self):
        url = reverse('customer_detail', kwargs={'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'})
        response = self.client.get(url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_valid_customer(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.groups.filter(name=WORKERS_GROUP_NAME).exists())

    def test_delete_invalid_customer(self):
        url = reverse('customer_detail', kwargs={'id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'})
        response = self.client.delete(url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def mock_get_value_side_effect(*args, **kwargs):
        if args[0] == k_first_name:
            return "John"
        elif args[0] == k_last_name:
            return "Doe"
        return None  # Default case

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=mock_get_value_side_effect)
    @patch('apps.core.utils.formatters.FormattingUtil.get_email', return_value='new_email@example.com')
    @patch('apps.core.utils.formatters.FormattingUtil.get_address', return_value=None)
    def test_put_valid_customer(self, mock_get_address, mock_get_email, mock_get_value):
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'new_email@example.com',
            'phone_number': '1234567890',
            'address': None,
            'billing_address': None,
            'tax_number': '123456789',
            'company': 'New Company'
        }
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'new_email@example.com')

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=DeserializationException('Invalid data'))
    def test_put_invalid_data(self, mock_get_value):
        data = {'first_name': 'John'}
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {'message': ['Invalid data']})

    @patch('apps.core.utils.formatters.FormattingUtil.get_value', side_effect=Exception('Server error'))
    def test_put_server_error(self, mock_get_value):
        data = {'first_name': 'John'}
        response = self.client.put(self.url, data, content_type='application/json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.json(), {'message': ['Server error']})


class CustomerSearchTermViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.group, created = Group.objects.get_or_create(name=CUSTOMERS_GROUP_NAME)
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@example.com')
        self.user.groups.add(self.group)
        self.user.save()
        self.url = reverse('customer_search_term', kwargs={'search_term': 'test'})
        self.client.force_login(self.user)

    @patch('apps.authentication.utils.customer_util.CustomerUtil.to_customer_view',
           side_effect=lambda customer: {'id': customer.id, 'email': customer.email})
    def test_get_customers_with_valid_search_term(self, mock_to_customer_view):
        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(k_customers, response.json())

    def test_get_customers_with_invalid_search_term(self):
        url = reverse('customer_search_term', kwargs={'search_term': 'invalid'})
        response = self.client.get(url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()[k_customers], [])

   


class OnboardingFlowViewTest(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123'
        )
        self.worker_profile = WorkerProfile.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.url = reverse('onboarding_flow')

    def test_onboarding_flow_success(self):
        data = {
            'car_washing_experience_type': 'beginner',
            'waiter_experience_type': 'beginner',
            'cleaning_experience_type': 'beginner',
            'chauffeur_experience_type': 'beginner',
            'gardening_experience_type': 'beginner',
            'situation_type': 'flexi',
            'work_type': 'weekday_mornings'
        }
        response = self.client.get(self.url, data, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.worker_profile.refresh_from_db()
        self.assertIn('job_types', response.data)

    def test_onboarding_flow_invalid_data(self):
        data = {
            'car_washing_experience_type': 'invalid_type'
        }
        response = self.client.get(self.url, data, format='json', headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WorkerProfileDetailViewTest(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123'
        )
        self.worker_profile = WorkerProfile.objects.create(user=self.user)
        self.dashboard_flow = DashboardFlow.objects.create(
            user=self.user,
            
        )
        self.url = reverse('worker_profile_detail', kwargs={'user_id': self.user.id})
        self.client.force_login(self.user)

    def test_get_worker_profile_detail(self):
        response = self.client.get(self.url, headers={"Client": settings.WORKER_GROUP_SECRET})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('worker_profile', response.data)
        self.assertIn('dashboard_flow', response.data)



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
      
        

class JWTBaseAuthViewTest(APITestCase):

    # Create a user
    # Authenticate the user with JwtAuthenticationView
    # Get the tokens from the view (Assert tokens are correct)
    # test the JWTBaseAuthView for confirmation

    def setUp(self):
        """ Set up test user and assign to a group. Set up a second user for testing invalid token cases"""

        # Set up groups with group client secret
        # -> Assumtions
        #Create user and assign to a group
        password, salt = EncryptionUtil.encrypt("password123")
        self.user = User.objects.create(username="testuser", email="testuser@example.com", password=password, salt=salt)
        self.group = Group.objects.get(name=WORKERS_GROUP_NAME)
        self.user.groups.add(self.group)
        self.user.save()
        print(f'user: {self.user}, {self.user.username}, {self.user.email}, {self.user.password}, {self.group.name}')

        #Create a second user for testing invalid token cases
        self.invalid_user = User.objects.create_user(username="invaliduser", password="invalidpassword", email="invaliduser@example.com")
    
    def authenticate_user(self):
        #Authenticate and get JWT tokens
        client_secret = settings.WORKER_GROUP_SECRET

        worker_profile = WorkerProfile.objects.create(user=self.user, accepted=True)

        url = reverse("token_obtain_pair")
        data = {"username":"testuser", "email":"testuser@example.com", "password":"password123"}
        headers = {"Client": client_secret}
        response = self.client.post(url, data, headers=headers, format="json")

        if response.status_code != 200:
            print(f"Authentication failed, Status code: {response.status_code}")
            print(f"Response content: {response.content.decode('utf-8')}")

        print(f"Data: {data}")
            
        #Assert that the response is successful and contains tokens
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data #return tokens for later use in the test
    

    def test_valid_authentication(self):
        """ Authenticate user and extract tokens """

        tokens = self.authenticate_user()
        access_token = tokens['access_token']
        print(f"Access token: {access_token}")

        #Use the JWT token to authenticate in JWTBaseAuthView
        auth_url = reverse("test_connection")
        headers = {'Authorization': access_token, 'Client': settings.WORKER_GROUP_SECRET}
        print(f"Worker Group Secret: {settings.WORKER_GROUP_SECRET}")
        

        response = self.client.get(auth_url, headers=headers)

        #Assert that the user is authenticated properly
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        #self.assertIn('user', response.data)
        


    def test_forbidden_authentication_invalid_token(self):
        """ Try authenticating with an invalid token. """

        tokens = self.authenticate_user()
        invalid_access_token = tokens='invalidtoken123'

        #Try accessing the JWTBaseAuthView with the invalid token
        auth_url = reverse("token_obtain_pair")
        headers = {'Authorization':f'Bearer {invalid_access_token}'}
        response = self.client.get(auth_url,  headers=headers)

        #Assert that the response is forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        print(f"Response content: {response.content.decode('utf-8')}")
    
    def test_user_not_in_group(self):
        """ Authenticate the user and assign to an invalid group. """

        tokens = self.authenticate_user()
        access_token = tokens['access_token']

        #Assign the invalid user to a different group
        self.invalid_user.groups.clear()
        self.invalid_user.groups.add(Group.objects.create(name="WORKERS_GROUP_NAME"))

        #Test the user is not in allowed group
        auth_url = reverse("token_obtain_pair")
        headers = {'Authorization':f'Bearer {access_token}'}
        response = self.client.get(auth_url,  headers=headers)

        #Assert that the response is forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        print(f"Response content: {response.content.decode('utf-8')}")


class ProfileMeViewTest(TestCase):
    """
    Tests retrieving and updating a authenticated user's profile.
    """
    profile_type = "customer"
    def setup(self):

        print("Setting up user and profile")

        self.client = APIClient()
        self.user, created = User.objects.update_or_create(
            username="testuser", 
            defaults={
                "email": "testuser@example.com", 
                "password": "password123"
            }
        )
        self.client.force_login(self.user)

        # Create an Address instance
        self.billing_address = Address.objects.create(
            street_name="123 Main St",
            house_number="45A",
            box_number="",
            city="Some City",
            zip_code="12345",
            country="Country Name",
            latitude=52.5200,
            longitude=13.4050
        )    
        # Create an Address instance
        self.customer_address = Address.objects.create(
            street_name="123 Main St",
            house_number="45A",
            box_number="",
            city="Some City",
            zip_code="12345",
            country="Country Name",
            latitude=52.5200,
            longitude=13.4050
        )    

        if self.profile_type == "customer":
            self.customer_profile = CustomerProfile.objects.create(
            user=self.user,
            tax_number = "123456789",
            company_name = "Test Company",
            customer_billing_address = self.billing_address,
            customer_address = self.customer_address,
            special_committee = "Test Committee"
            )
        elif self.profile_type == "worker":
             self.worker_profile = WorkerProfile.objects.create(
            user=self.user,
            iban="DE89370400440532013000",
            ssn="123-45-6789",
            worker_type="freelancer",
            date_of_birth=datetime.datetime.now(),
            place_of_birth="Candyland",
            worker_address=address
            )
        elif self.profile_type == "admin":
            self.admin_profile = AdminProfile.objects.create(
            user = self.user,
            session_duration = 3600
            )
    
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
       
    
    def test_get_profile_authorized(self):
        """Test to GET profile for an authenticated user"""
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile_me"))

        print(f"status code: {response.status_code}")
        print(f"Content: {response.content}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("user_id", response.data)

    def test_get_profile_unauthorized(self):
        self.client.logout()
        """Test to GET profile without authentication"""
        response = self.client.get(reverse("profile_me"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_profile_invalid_user(self):
        """Test to GET profile with a non-existing user"""
        self.client.logout()
        response = self.client.get(reverse("profile_me"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_profile_valid_data(self):
        """Test to PUT profile with valid data"""
        self.client.force_login(self.user)
        response = self.client.put(reverse("profile_me"), {
            "first_name": "UpdatedName",
            "last_name": "UpdatedLast",
            "email": "test@example.com"
        }, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "UpdatedName")

    def test_put_profile_invalid_format(self):
        """Test to PUT profile with invalid data format"""
        self.client.force_login(self.user)
        response = self.client.put(reverse("profile_me"), {
            "email":"not-an-email"
        }, format="json")
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        

    def test_put_profile_unauthorized(self):
        """Test to PUT profile without authentication"""
        self.client.logout()
        response = self.client.put(reverse("profile_me"), {
            "first_name": "NewName"
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)





       
        