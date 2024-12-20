from unittest.mock import patch

from apps.core.assumptions import *
from apps.core.model_exceptions import DeserializationException
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.services.contract_service import JobApplicationService
from apps.jobs.services.job_service import JobService
from django.http import Http404
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class JobViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('job-details', kwargs={'id': 'test-job-id'})
        self.job_details = {'id': 'test-job-id', 'title': 'Test Job'}

    @patch.object(JobService, 'get_job_details')
    def test_get_job_details(self, mock_get_job_details):
        mock_get_job_details.return_value = self.job_details
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.job_details)

    @patch.object(JobService, 'delete_job')
    def test_delete_job(self, mock_delete_job):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_delete_job.assert_called_once_with('test-job-id')

    @patch.object(JobService, 'delete_job')
    def test_delete_job_not_found(self, mock_delete_job):
        mock_delete_job.side_effect = Http404
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(JobService, 'update_job')
    def test_update_job(self, mock_update_job):
        update_data = {'title': 'Updated Job'}
        response = self.client.put(self.url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_update_job.assert_called_once_with('test-job-id', update_data)

    @patch.object(JobService, 'update_job')
    def test_update_job_bad_request(self, mock_update_job):
        mock_update_job.side_effect = DeserializationException('Invalid data')
        response = self.client.put(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('message', response.data)

    @patch.object(JobService, 'update_job')
    def test_update_job_internal_server_error(self, mock_update_job):
        mock_update_job.side_effect = Exception('Server error')
        response = self.client.put(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('message', response.data)


class CreateJobViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('create-job')
        self.valid_data = {'title': 'New Job'}
        self.invalid_data = {}

    @patch.object(JobService, 'create_job')
    def test_create_job_success(self, mock_create_job):
        mock_create_job.return_value = 'new-job-id'
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_job_id: 'new-job-id'})

    @patch.object(JobService, 'create_job')
    def test_create_job_bad_request(self, mock_create_job):
        mock_create_job.side_effect = DeserializationException('Invalid data')
        response = self.client.post(self.url, self.invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)

    @patch.object(JobService, 'create_job')
    def test_create_job_internal_server_error(self, mock_create_job):
        mock_create_job.side_effect = Exception('Server error')
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn(k_message, response.data)


class UpcomingJobsViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('upcoming-jobs')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_upcoming_jobs')
    def test_get_upcoming_jobs(self, mock_get_upcoming_jobs):
        mock_get_upcoming_jobs.return_value = self.jobs
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class AllUpcomingJobsViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('all-upcoming-jobs')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_upcoming_jobs')
    def test_get_all_upcoming_jobs(self, mock_get_upcoming_jobs):
        mock_get_upcoming_jobs.return_value = self.jobs
        response = self.client.get(self.url, {'start': '2023-01-01', 'end': '2023-12-31'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class HistoryJobsViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('history-jobs')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_history_jobs')
    def test_get_history_jobs(self, mock_get_history_jobs):
        mock_get_history_jobs.return_value = self.jobs
        response = self.client.get(self.url, {'start': '0', 'end': '9999999999'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class GetJobsBasedOnUserViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('get-jobs-based-on-user')
        self.valid_data = {k_worker_id: 'worker1', k_customer_id: 'customer1'}
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_jobs_based_on_user')
    def test_get_jobs_based_on_user_success(self, mock_get_jobs_based_on_user):
        mock_get_jobs_based_on_user.return_value = self.jobs
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})

    @patch.object(FormattingUtil, 'get_value')
    def test_get_jobs_based_on_user_bad_request(self, mock_get_value):
        mock_get_value.side_effect = DeserializationException('Invalid data')
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)

    @patch.object(FormattingUtil, 'get_value')
    def test_get_jobs_based_on_user_internal_server_error(self, mock_get_value):
        mock_get_value.side_effect = Exception('Server error')
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn(k_message, response.data)


class TimeRegistrationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('time-registration')
        self.valid_data = {k_job_id: 'job1'}
        self.times = [{'id': 'time1', 'hours': 5}, {'id': 'time2', 'hours': 3}]

    @patch.object(JobService, 'get_time_registrations')
    def test_get_time_registrations_success(self, mock_get_time_registrations):
        mock_get_time_registrations.return_value = self.times
        response = self.client.get(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_times: self.times})

    @patch.object(FormattingUtil, 'get_value')
    def test_get_time_registrations_bad_request(self, mock_get_value):
        mock_get_value.side_effect = Exception('Invalid data')
        response = self.client.get(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)

    @patch.object(JobService, 'register_time')
    def test_post_time_registration_success(self, mock_register_time):
        mock_register_time.return_value = 'job1'
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_job_id: 'job1'})

    @patch.object(JobService, 'register_time')
    def test_post_time_registration_bad_request(self, mock_register_time):
        mock_register_time.side_effect = DeserializationException('Invalid data')
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)


class SignTimeRegistrationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('sign-time-registration')
        self.valid_data = {'some_key': 'some_value'}

    @patch.object(JobService, 'sign_time_registration')
    def test_post_sign_time_registration_success(self, mock_sign_time_registration):
        mock_sign_time_registration.return_value = 'time_registration_id'
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_id: 'time_registration_id'})

    @patch.object(JobService, 'sign_time_registration')
    def test_post_sign_time_registration_bad_request(self, mock_sign_time_registration):
        mock_sign_time_registration.side_effect = DeserializationException('Invalid data')
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)

    @patch.object(JobService, 'sign_time_registration')
    def test_post_sign_time_registration_internal_server_error(self, mock_sign_time_registration):
        mock_sign_time_registration.side_effect = Exception('Server error')
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn(k_message, response.data)


class ActiveJobListTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('active-job-list')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_active_jobs')
    def test_get_active_jobs(self, mock_get_active_jobs):
        mock_get_active_jobs.return_value = self.jobs
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class DoneJobListTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('done-job-list')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_done_jobs')
    def test_get_done_jobs(self, mock_get_done_jobs):
        mock_get_done_jobs.return_value = self.jobs
        response = self.client.get(self.url, {'start': '2023-01-01', 'end': '2023-12-31'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class DraftJobListTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('draft-job-list')
        self.jobs = [{'id': 'job1', 'title': 'Job 1'}, {'id': 'job2', 'title': 'Job 2'}]

    @patch.object(JobService, 'get_draft_jobs')
    def test_get_draft_jobs(self, mock_get_draft_jobs):
        mock_get_draft_jobs.return_value = self.jobs
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_jobs: self.jobs})


class ApplicationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('application-details', kwargs={'id': 'application_id'})
        self.application_data = {'id': 'application_id', 'title': 'Application Title'}

    @patch.object(JobApplicationService, 'get_application_details')
    def test_get_application_details(self, mock_get_application_details):
        mock_get_application_details.return_value = self.application_data
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, self.application_data)

    @patch.object(JobApplicationService, 'get_application_details')
    def test_get_application_details_not_found(self, mock_get_application_details):
        mock_get_application_details.side_effect = KeyError
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(JobApplicationService, 'delete_application')
    def test_delete_application(self, mock_delete_application):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_delete_application.assert_called_once_with('application_id')

    @patch.object(JobApplicationService, 'delete_application')
    def test_delete_application_not_found(self, mock_delete_application):
        mock_delete_application.side_effect = KeyError
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ApproveApplicationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('approve-application', kwargs={'id': 'application_id'})

    @patch.object(JobApplicationService, 'approve_application')
    def test_post_approve_application_success(self, mock_approve_application):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_approve_application.assert_called_once_with('application_id')

    @patch.object(JobApplicationService, 'approve_application')
    def test_post_approve_application_not_found(self, mock_approve_application):
        mock_approve_application.side_effect = KeyError
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DenyApplicationViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('deny-application', kwargs={'id': 'application_id'})

    @patch.object(JobApplicationService, 'deny_application')
    def test_post_deny_application_success(self, mock_deny_application):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_deny_application.assert_called_once_with('application_id')

    @patch.object(JobApplicationService, 'deny_application')
    def test_post_deny_application_not_found(self, mock_deny_application):
        mock_deny_application.side_effect = KeyError
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MyApplicationsViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('my-applications')
        self.application_model_list = [{'id': 'app1', 'title': 'Application 1'},
                                       {'id': 'app2', 'title': 'Application 2'}]
        self.valid_data = {'some_key': 'some_value'}

    @patch.object(JobApplicationService, 'get_my_applications')
    def test_get_my_applications_success(self, mock_get_my_applications):
        mock_get_my_applications.return_value = self.application_model_list
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_applications: self.application_model_list})

    @patch.object(JobApplicationService, 'create_application')
    def test_post_create_application_success(self, mock_create_application):
        mock_create_application.return_value = 'application_id'
        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {k_id: 'application_id'})

    @patch.object(JobApplicationService, 'create_application')
    def test_post_create_application_bad_request(self, mock_create_application):
        mock_create_application.side_effect = DeserializationException('Invalid data')
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(k_message, response.data)


class ApplicationsListViewTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('applications-list', kwargs={'job_id': 'job1'})
        self.applications = [{'id': 'app1', 'title': 'Application 1'}, {'id': 'app2', 'title': 'Application 2'}]

    @patch.object(JobApplicationService, 'get_applications_list')
    def test_get_applications_list_success(self, mock_get_applications_list):
        mock_get_applications_list.return_value = self.applications
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[k_applications], self.applications)
        self.assertEqual(response.data[k_items_per_page], 25)
        self.assertEqual(response.data[k_total], len(self.applications))
