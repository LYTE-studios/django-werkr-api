# src/apps/notifications/tests/test_email_service.py

from django.test import TestCase
from unittest.mock import patch
from django.conf import settings
from apps.notifications.models.mail_template import (
    ApprovedMailTemplate,
    CodeMailTemplate,
    DeniedMailTemplate,
    MailTemplate,
    SelectedWorkerTemplate,
    TimeRegisteredTemplate,
    CancelledMailTemplate,
)


class EmailTemplateServiceTests(TestCase):
    def setUp(self):
        # Sample data for testing
        self.test_recipients = [{"Email": "test@example.com", "Name": "Test User"}]
        self.test_data = {
            "user_name": "John Doe",
            "job_title": "Web Development",
        }

    def test_approved_template_creation(self):
        template = ApprovedMailTemplate()
        self.assertEqual(template.template_id, 5792978)
        self.assertEqual(template.subject, "Get A Wash | You've been approved!")

    def test_code_mail_template_creation(self):
        template = CodeMailTemplate()
        self.assertEqual(template.template_id, 5798048)
        self.assertEqual(template.subject, "Password reset code")

    def test_denied_template_creation(self):
        template = DeniedMailTemplate()
        self.assertEqual(template.template_id, 5771049)
        self.assertEqual(template.subject, "Get A Wash | Job was full!")

    def test_selected_washer_template_creation(self):
        template = SelectedWorkerTemplate()
        self.assertEqual(template.template_id, 6150888)
        self.assertEqual(
            template.subject, "Get A Wash | A washer has been selected for your job!"
        )

    @patch("mailjet_rest.Client")
    def test_send_template_email_task(self, mock_mailjet_client):
        # Mock the Mailjet client response
        mock_response = mock_mailjet_client.return_value.send.create.return_value
        mock_response.status_code = 200

        # Call the task directly
        result = MailTemplate().send(
            recipients=self.test_recipients, data=self.test_data
        )

        # Assert the task was successful
        self.assertTrue(result)

        # Verify Mailjet client was called with correct data
        mock_mailjet_client.return_value.send.create.assert_called_once_with(
            data={
                "Messages": [
                    {
                        "From": {
                            "Email": settings.DEFAULT_FROM_EMAIL,
                            "Name": settings.DEFAULT_FROM_NAME,
                        },
                        "To": self.test_recipients,
                        "Subject": "Get A Wash | You've been approved!",
                        "TemplateID": 5792978,
                        "TemplateLanguage": True,
                        "Variables": self.test_data,
                    },
                ],
            }
        )

    @patch("mailjet_rest.Client")
    def test_send_template_email_task_failure(self, mock_mailjet_client):
        # Simulate a failed email send
        mock_response = mock_mailjet_client.return_value.send.create.return_value
        mock_response.status_code = 400

        # Call the task directly
        result = MailTemplate().send(
            recipients=self.test_recipients, data=self.test_data
        )

        # Assert the task failed
        self.assertFalse(result)

    def test_all_templates_have_unique_ids(self):
        templates = [
            ApprovedMailTemplate(),
            CodeMailTemplate(),
            DeniedMailTemplate(),
            SelectedWorkerTemplate(),
            TimeRegisteredTemplate(),
            CancelledMailTemplate(),
        ]

        # Collect template IDs
        template_ids = [template.template_id for template in templates]

        # Assert all IDs are unique
        self.assertEqual(
            len(template_ids),
            len(set(template_ids)),
            "All email template IDs must be unique",
        )

    def test_template_data_variables(self):
        # Test that all templates can be instantiated with data
        templates = [
            ApprovedMailTemplate(),
            CodeMailTemplate(),
            DeniedMailTemplate(),
            SelectedWorkerTemplate(),
            TimeRegisteredTemplate(),
            CancelledMailTemplate(),
        ]

        for template in templates:
            try:
                template.send(
                    recipients=[{"Email": "test@example.com"}],
                    data={"test_key": "test_value"},
                )
            except Exception as e:
                self.fail(
                    f"Template {template.__class__.__name__} failed to send: {str(e)}"
                )
