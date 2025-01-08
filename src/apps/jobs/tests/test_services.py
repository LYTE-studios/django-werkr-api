# file: src/apps/jobs/tests/test_job_application_service.py

from unittest.mock import patch, MagicMock

from apps.jobs.models import JobApplication, JobApplicationState, Job
from apps.jobs.services.contract_service import JobApplicationService
from django.test import TestCase


class JobApplicationServiceTest(TestCase):

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    def test_get_application_details(self, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_application.to_model_view.return_value = {'id': 'application_id'}
        mock_get_object_or_404.return_value = mock_application

        result = JobApplicationService.get_application_details('application_id')
        self.assertEqual(result, {'id': 'application_id'})
        mock_get_object_or_404.assert_called_once_with(JobApplication, id='application_id')

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    def test_delete_application(self, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.delete_application('application_id')
        self.assertEqual(mock_application.application_state, JobApplicationState.rejected)
        mock_application.save.assert_called_once()

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    @patch('apps.jobs.services.contract_service.JobManager.approve_application')
    def test_approve_application(self, mock_approve_application, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.approve_application('application_id')
        mock_approve_application.assert_called_once_with(mock_application)
        mock_application.job.save.assert_called_once()
        mock_application.save.assert_called_once()

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    @patch('apps.jobs.services.contract_service.JobManager.deny_application')
    def test_deny_application(self, mock_deny_application, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.deny_application('application_id')
        mock_deny_application.assert_called_once_with(mock_application)
        mock_application.job.save.assert_called_once()
        mock_application.save.assert_called_once()

    @patch('apps.jobs.services.contract_service.requests.post')
    def test_fetch_directions(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b'directions'
        mock_post.return_value = mock_response

        result = JobApplicationService.fetch_directions(1.0, 2.0, 3.0, 4.0)
        self.assertEqual(result, mock_response)
        mock_post.assert_called_once()

    @patch('apps.jobs.services.contract_service.JobApplication.objects.filter')
    def test_get_my_applications(self, mock_filter):
        mock_user = MagicMock()
        mock_user.id = 'user_id'
        mock_application = MagicMock()
        mock_application.to_model_view.return_value = {'id': 'application_id'}
        mock_filter.return_value = [mock_application]

        result = JobApplicationService.get_my_applications(mock_user)
        self.assertEqual(result, [{'id': 'application_id'}])

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    @patch('apps.jobs.services.contract_service.FormattingUtil')
    @patch('apps.jobs.services.contract_service.FavoriteAddress')
    @patch('apps.jobs.services.contract_service.JobManager.apply')
    def test_create_application(self, mock_apply, mock_favorite_address, mock_formatting_util, mock_get_object_or_404):
        mock_user = MagicMock()
        mock_user.id = 'user_id'
        mock_data = {'some_key': 'some_value'}
        mock_job = MagicMock()
        mock_job.selected_workers = 5
        mock_job.max_workers = 10
        mock_address = MagicMock()
        mock_formatting_util.return_value.get_value.side_effect = ['job_id', 'address_title', 'note', None]
        mock_formatting_util.return_value.get_address.return_value = mock_address
        mock_formatting_util.return_value.get_bool.return_value = False
        mock_get_object_or_404.side_effect = [mock_job, mock_job]

        result = JobApplicationService.create_application(mock_data, mock_user)
        self.assertIsNotNone(result)
        mock_apply.assert_called_once()

    @patch('apps.jobs.services.contract_service.get_object_or_404')
    @patch('apps.jobs.services.contract_service.JobApplication.objects.filter')
    def test_get_applications_list(self, mock_filter, mock_get_object_or_404):
        mock_job = MagicMock()
        mock_application = MagicMock()
        mock_filter.return_value = [mock_application]
        mock_get_object_or_404.return_value = mock_job

        result = JobApplicationService.get_applications_list('job_id')
        self.assertEqual(result, [mock_application])
        mock_get_object_or_404.assert_called_once_with(Job, id='job_id')
