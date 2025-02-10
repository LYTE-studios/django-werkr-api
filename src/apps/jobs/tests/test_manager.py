import datetime
from django.test import TestCase
from unittest.mock import patch
from apps.jobs.models import Job, JobApplication, JobApplicationState
from apps.jobs.managers.job_manager import JobManager
from apps.notifications.models import (
    ApprovedMailTemplate,
    DeniedMailTemplate,
    SelectedWorkerTemplate,
)
from apps.legal.services.dimona_service import DimonaService
from apps.legal.utils.contract_util import ContractUtil
from apps.notifications.managers.notification_manager import NotificationManager
from apps.core.models.geo import Address
from django.contrib.auth import get_user_model

User = get_user_model()


class JobManagerTest(TestCase):
    def setUp(self):
        self.job = Job.objects.create(
            title="Test Job",
            max_workers=5,
            selected_workers=0,
            start_time=datetime.datetime.now(),
            end_time=datetime.datetime.now() + datetime.timedelta(hours=8),
            address=Address.objects.create(
                street="123 Test St",
                city="Test City",
                state="Test State",
                zip_code="12345",
                country="Test Country",
            ),
        )
        self.application = JobApplication.objects.create(
            job=self.job,
            worker=User.objects.create_user(
                username="testuser",
                email="testuser@example.com",
                password="password123",
            ),
            application_state=JobApplicationState.pending,
        )

    @patch.object(DimonaService, "cancel_dimona")
    @patch.object(DeniedMailTemplate, "send")
    @patch.object(NotificationManager, "create_notification_for_user")
    def test_deny_application(
        self, mock_create_notification, mock_send_mail, mock_cancel_dimona
    ):
        JobManager.deny_application(self.application)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.application_state, JobApplicationState.rejected
        )
        mock_cancel_dimona.assert_called_once_with(self.application)
        mock_send_mail.assert_called_once()
        mock_create_notification.assert_called_once()

    @patch.object(ApprovedMailTemplate, "send")
    @patch.object(NotificationManager, "create_notification_for_user")
    @patch.object(SelectedWorkerTemplate, "send")
    def test_notify_approved_worker(
        self,
        mock_send_selected_worker_mail,
        mock_create_notification,
        mock_send_approved_mail,
    ):
        JobManager._notify_approved_worker(self.application)
        mock_send_approved_mail.assert_called_once()
        mock_create_notification.assert_called_once()
        mock_send_selected_worker_mail.assert_called_once()

    @patch.object(DimonaService, "create_dimona")
    @patch.object(ContractUtil, "generate_contract")
    def test_approve_application(self, mock_generate_contract, mock_create_dimona):
        JobManager.approve_application(self.application)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.application_state, JobApplicationState.approved
        )
        mock_create_dimona.assert_called_once_with(self.application)
        mock_generate_contract.assert_called_once_with(self.application)

    def test_calculate_selected_workers(self):
        self.application.application_state = JobApplicationState.approved
        self.application.save()
        count = JobManager.calculate_selected_workers(self.application)
        self.assertEqual(count, 1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.selected_workers, 1)

    def test_apply(self):
        application = JobManager.apply(self.application)
        self.assertIsNotNone(application.id)

    @patch("asyncio.create_task")
    def test_send_job_notification(self, mock_create_task):
        JobManager._send_job_notification(self.job)
        mock_create_task.assert_called_once()

    def test_get_overlap_applications(self):
        overlap_applications = JobManager.get_overlap_applications(self.application)
        self.assertIn(self.application, overlap_applications)

    def test_get_end_overlap_applications(self):
        end_overlap_applications = JobManager.get_end_overlap_applications(
            self.application
        )
        self.assertIn(self.application, end_overlap_applications)

    def test_remove_overlap_applications(self):
        JobManager.remove_overlap_applications(self.application)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.application_state, JobApplicationState.rejected
        )

    def test_create_job(self):
        job = JobManager.create(self.job)
        self.assertIsNotNone(job.id)
        self.assertEqual(job.selected_workers, 0)
