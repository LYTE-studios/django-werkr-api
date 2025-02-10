# file: src/apps/jobs/tests/test_job_application_service.py

from unittest.mock import patch, MagicMock
from apps.jobs.services.contract_service import JobApplicationService
from django.test import TestCase
import datetime
from apps.jobs.services.statistics_service import StatisticsService
from apps.jobs.services.job_service import JobService
from apps.jobs.models import (
    Job,
    JobApplication,
    JobApplicationState,
    JobState,
    TimeRegistration,
)


class JobApplicationServiceTest(TestCase):

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    def test_get_application_details(self, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_application.to_model_view.return_value = {"id": "application_id"}
        mock_get_object_or_404.return_value = mock_application

        result = JobApplicationService.get_application_details("application_id")
        self.assertEqual(result, {"id": "application_id"})
        mock_get_object_or_404.assert_called_once_with(
            JobApplication, id="application_id"
        )

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    def test_delete_application(self, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.delete_application("application_id")
        self.assertEqual(
            mock_application.application_state, JobApplicationState.rejected
        )
        mock_application.save.assert_called_once()

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    @patch("apps.jobs.services.contract_service.JobManager.approve_application")
    def test_approve_application(
        self, mock_approve_application, mock_get_object_or_404
    ):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.approve_application("application_id")
        mock_approve_application.assert_called_once_with(mock_application)
        mock_application.job.save.assert_called_once()
        mock_application.save.assert_called_once()

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    @patch("apps.jobs.services.contract_service.JobManager.deny_application")
    def test_deny_application(self, mock_deny_application, mock_get_object_or_404):
        mock_application = MagicMock()
        mock_get_object_or_404.return_value = mock_application

        JobApplicationService.deny_application("application_id")
        mock_deny_application.assert_called_once_with(mock_application)
        mock_application.job.save.assert_called_once()
        mock_application.save.assert_called_once()

    @patch("apps.jobs.services.contract_service.requests.post")
    def test_fetch_directions(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b"directions"
        mock_post.return_value = mock_response

        result = JobApplicationService.fetch_directions(1.0, 2.0, 3.0, 4.0)
        self.assertEqual(result, mock_response)
        mock_post.assert_called_once()

    @patch("apps.jobs.services.contract_service.JobApplication.objects.filter")
    def test_get_my_applications(self, mock_filter):
        mock_user = MagicMock()
        mock_user.id = "user_id"
        mock_application = MagicMock()
        mock_application.to_model_view.return_value = {"id": "application_id"}
        mock_filter.return_value = [mock_application]

        result = JobApplicationService.get_my_applications(mock_user)
        self.assertEqual(result, [{"id": "application_id"}])

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    @patch("apps.jobs.services.contract_service.FormattingUtil")
    @patch("apps.jobs.services.contract_service.FavoriteAddress")
    @patch("apps.jobs.services.contract_service.JobManager.apply")
    def test_create_application(
        self,
        mock_apply,
        mock_favorite_address,
        mock_formatting_util,
        mock_get_object_or_404,
    ):
        mock_user = MagicMock()
        mock_user.id = "user_id"
        mock_data = {"some_key": "some_value"}
        mock_job = MagicMock()
        mock_job.selected_workers = 5
        mock_job.max_workers = 10
        mock_address = MagicMock()
        mock_formatting_util.return_value.get_value.side_effect = [
            "job_id",
            "address_title",
            "note",
            None,
        ]
        mock_formatting_util.return_value.get_address.return_value = mock_address
        mock_formatting_util.return_value.get_bool.return_value = False
        mock_get_object_or_404.side_effect = [mock_job, mock_job]

        result = JobApplicationService.create_application(mock_data, mock_user)
        self.assertIsNotNone(result)
        mock_apply.assert_called_once()

    @patch("apps.jobs.services.contract_service.get_object_or_404")
    @patch("apps.jobs.services.contract_service.JobApplication.objects.filter")
    def test_get_applications_list(self, mock_filter, mock_get_object_or_404):
        mock_job = MagicMock()
        mock_application = MagicMock()
        mock_filter.return_value = [mock_application]
        mock_get_object_or_404.return_value = mock_job

        result = JobApplicationService.get_applications_list("job_id")
        self.assertEqual(result, [mock_application])
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")


class StatisticsServiceTest(TestCase):

    @patch("apps.jobs.services.statistics_service.Job.objects.filter")
    @patch("apps.jobs.services.statistics_service.TimeRegistration.objects.filter")
    def test_get_weekly_stats(self, mock_time_registration_filter, mock_job_filter):
        worker_id = 1
        week_start = datetime.date(2023, 1, 1)
        week_end = datetime.date(2023, 1, 7)

        mock_job = MagicMock()
        mock_job_filter.return_value = [mock_job]
        mock_time_registration = MagicMock()
        mock_time_registration_filter.return_value = [mock_time_registration]

        mock_time_registration.annotate.return_value.aggregate.return_value = {
            "total_duration": datetime.timedelta(hours=10)
        }
        mock_job_filter.return_value.filter.return_value.annotate.return_value.aggregate.return_value = {
            "total_duration": datetime.timedelta(hours=5)
        }
        mock_job_filter.return_value.filter.return_value.count.side_effect = [2, 3]

        result = StatisticsService.get_weekly_stats(worker_id, week_start, week_end)

        self.assertEqual(result["total_worked_hours"], 10)
        self.assertEqual(result["total_upcoming_hours"], 5)
        self.assertEqual(result["completed_jobs_count"], 2)
        self.assertEqual(result["upcoming_jobs_count"], 3)
        self.assertEqual(result["average_hours"], 1)
        self.assertIn("Mon", result["daily_hours"])

    @patch("apps.jobs.services.statistics_service.Job.objects.filter")
    @patch("apps.jobs.services.statistics_service.TimeRegistration.objects.filter")
    def test_get_monthly_stats(self, mock_time_registration_filter, mock_job_filter):
        worker_id = 1
        year = 2023

        mock_job = MagicMock()
        mock_job_filter.return_value = [mock_job]
        mock_time_registration = MagicMock()
        mock_time_registration_filter.return_value = [mock_time_registration]

        mock_time_registration.annotate.return_value.aggregate.return_value = {
            "total_duration": datetime.timedelta(hours=10)
        }
        mock_job_filter.return_value.filter.return_value.annotate.return_value.aggregate.return_value = {
            "total_duration": datetime.timedelta(hours=5)
        }
        mock_job_filter.return_value.filter.return_value.count.side_effect = [2, 3] * 12

        result = StatisticsService.get_monthly_stats(worker_id, year)

        self.assertEqual(result["year"], 2023)
        self.assertIn("Jan", result["monthly_stats"])
        self.assertEqual(result["completed_jobs_count"], 24)
        self.assertEqual(result["upcoming_jobs_count"], 36)
        self.assertEqual(result["monthly_stats"]["Jan"]["average_hours"], 10)
        self.assertEqual(result["monthly_stats"]["Jan"]["total_upcoming_hours"], 5)


class JobServiceTest(TestCase):

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_job_details(self, mock_to_model_view, mock_get_object_or_404):
        mock_job = MagicMock()
        mock_get_object_or_404.return_value = mock_job
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_job_details("job_id")
        self.assertEqual(result, {"id": "job_id"})
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")
        mock_to_model_view.assert_called_once_with(mock_job)

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.JobApplication.objects.filter")
    @patch(
        "apps.jobs.services.job_service.NotificationManager.create_notification_for_user"
    )
    @patch("apps.jobs.services.job_service.CancelledMailTemplate.send")
    def test_delete_job(
        self, mock_send, mock_create_notification, mock_filter, mock_get_object_or_404
    ):
        mock_job = MagicMock()
        mock_get_object_or_404.return_value = mock_job
        mock_application = MagicMock()
        mock_filter.return_value = [mock_application]

        JobService.delete_job("job_id")
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")
        self.assertTrue(mock_job.archived)
        self.assertEqual(mock_job.selected_workers, 0)
        mock_job.save.assert_called_once_with(
            update_fields=["archived", "selected_workers"]
        )
        mock_filter.assert_called_once_with(
            job_id=mock_job.id, application_state=JobApplicationState.approved
        )
        mock_application.save.assert_called_once()
        mock_create_notification.assert_called_once()
        mock_send.assert_called_once()

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.FormattingUtil")
    def test_update_job(self, mock_formatting_util, mock_get_object_or_404):
        mock_job = MagicMock()
        mock_get_object_or_404.return_value = mock_job
        mock_formatter = MagicMock()
        mock_formatting_util.return_value = mock_formatter
        mock_formatter.get_value.side_effect = ["title", "customer_id", "description"]
        mock_formatter.get_date.side_effect = [
            datetime.datetime.now(),
            datetime.datetime.now(),
            datetime.datetime.now(),
            datetime.datetime.now(),
        ]
        mock_formatter.get_address.return_value = MagicMock()
        mock_formatter.get_bool.return_value = True

        JobService.update_job("job_id", {})
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")
        mock_job.save.assert_called_once()

    @patch("apps.jobs.services.job_service.FormattingUtil")
    @patch("apps.jobs.services.job_service.JobManager.create")
    def test_create_job(self, mock_create, mock_formatting_util):
        mock_formatter = MagicMock()
        mock_formatting_util.return_value = mock_formatter
        mock_formatter.get_value.side_effect = ["title", "customer_id", "description"]
        mock_formatter.get_date.side_effect = [
            datetime.datetime.now(),
            datetime.datetime.now(),
            datetime.datetime.now(),
            datetime.datetime.now(),
        ]
        mock_formatter.get_address.return_value = MagicMock()
        mock_formatter.get_bool.return_value = True

        result = JobService.create_job({})
        self.assertIsNotNone(result)
        mock_create.assert_called_once()

    @patch("apps.jobs.services.job_service.Job.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_upcoming_jobs(self, mock_to_model_view, mock_filter):
        mock_job = MagicMock()
        mock_filter.return_value = [mock_job]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_upcoming_jobs(MagicMock())
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_job)

    @patch("apps.jobs.services.job_service.JobApplication.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_history_jobs(self, mock_to_model_view, mock_filter):
        mock_application = MagicMock()
        mock_filter.return_value = [mock_application]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_history_jobs(
            MagicMock(), datetime.datetime.now(), datetime.datetime.now()
        )
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_application.job)

    @patch("apps.jobs.services.job_service.Job.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_jobs_based_on_user(self, mock_to_model_view, mock_filter):
        mock_job = MagicMock()
        mock_filter.return_value = [mock_job]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_jobs_based_on_user(worker_id="worker_id")
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_job)

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.TimeRegistration.objects.filter")
    def test_get_time_registrations(self, mock_filter, mock_get_object_or_404):
        mock_job = MagicMock()
        mock_get_object_or_404.return_value = mock_job
        mock_time_registration = MagicMock()
        mock_filter.return_value = [mock_time_registration]

        result = JobService.get_time_registrations("job_id")
        self.assertEqual(result, [mock_time_registration.to_model_view()])
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")
        mock_filter.assert_called_once_with(job_id="job_id")

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.FormattingUtil")
    @patch("apps.jobs.services.job_service.TimeRegisteredTemplate.send")
    def test_register_time(
        self, mock_send, mock_formatting_util, mock_get_object_or_404
    ):
        mock_job = MagicMock()
        mock_get_object_or_404.return_value = mock_job
        mock_formatter = MagicMock()
        mock_formatting_util.return_value = mock_formatter
        mock_formatter.get_value.side_effect = ["job_id", "start_time", "end_time"]
        mock_formatter.get_time.return_value = None
        mock_formatter.get_bool.return_value = True

        result = JobService.register_time({}, MagicMock())
        self.assertIsNotNone(result)
        mock_get_object_or_404.assert_called_once_with(Job, id="job_id")
        mock_send.assert_called_once()

    @patch("apps.jobs.services.job_service.get_object_or_404")
    @patch("apps.jobs.services.job_service.FormattingUtil")
    def test_sign_time_registration(self, mock_formatting_util, mock_get_object_or_404):
        mock_time_registration = MagicMock()
        mock_get_object_or_404.return_value = mock_time_registration
        mock_formatter = MagicMock()
        mock_formatting_util.return_value = mock_formatter
        mock_formatter.get_value.side_effect = ["id"]

        result = JobService.sign_time_registration({})
        self.assertIsNotNone(result)
        mock_get_object_or_404.assert_called_once_with(TimeRegistration, id="id")
        mock_time_registration.save.assert_called_once()

    @patch("apps.jobs.services.job_service.Job.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_active_jobs(self, mock_to_model_view, mock_filter):
        mock_job = MagicMock()
        mock_filter.return_value = [mock_job]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_active_jobs()
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_job)

    @patch("apps.jobs.services.job_service.Job.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_done_jobs(self, mock_to_model_view, mock_filter):
        mock_job = MagicMock()
        mock_filter.return_value = [mock_job]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_done_jobs(
            datetime.datetime.now(), datetime.datetime.now()
        )
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_job)

    @patch("apps.jobs.services.job_service.Job.objects.filter")
    @patch("apps.jobs.services.job_service.JobUtil.to_model_view")
    def test_get_draft_jobs(self, mock_to_model_view, mock_filter):
        mock_job = MagicMock()
        mock_filter.return_value = [mock_job]
        mock_to_model_view.return_value = {"id": "job_id"}

        result = JobService.get_draft_jobs()
        self.assertEqual(result, [{"id": "job_id"}])
        mock_filter.assert_called_once()
        mock_to_model_view.assert_called_once_with(mock_job)
