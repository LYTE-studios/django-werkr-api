from celery import shared_task
from mailjet_rest import Client
from django.conf import settings


class MailTemplate:
    template_id: int = 5794325
    subject: str = 'Get A Wash | New message'

    api_key = settings.MAILJET_API_KEY
    api_secret = settings.MAILJET_API_SECRET

    def send(self, recipients: list[str], data: dict):
        """Sends email asynchronously"""
        self.send_task.delay(
            template_id=self.template_id,
            subject=self.subject,
            recipients=recipients,
            data=data
        )

    @shared_task
    def send_task(self, recipients: list[str], data: dict):
        """Celery task to send emails asynchronously"""
        try:
            mailjet = Client(auth=(self.api_key, self.api_secret), version='v3.1')

            response = mailjet.send.create(
                data={
                    'Messages': [
                        {
                            "From": {
                                "Email": settings.DEFAULT_FROM_EMAIL,
                                "Name": settings.DEFAULT_FROM_NAME
                            },
                            "To": recipients,
                            "Subject": self.subject,
                            "TemplateID": self.template_id,
                            "TemplateLanguage": True,
                            "Variables": data,
                        },
                    ],
                },
            )

            return response.status_code == 200

        except Exception as e:
            # Log the error but don't raise it
            print(f"Error sending email: {str(e)}")
            return False

    def to_data(self, recipient: dict, extra_data: dict):
        """Converts template data into the required format"""
        return {
            'Messages': [
                {
                    "From": {
                        "Email": settings.DEFAULT_FROM_EMAIL,
                        "Name": settings.DEFAULT_FROM_NAME
                    },
                    "To": [recipient],
                    "Subject": self.subject,
                    "TemplateID": self.template_id,
                    "TemplateLanguage": True,
                    "Variables": extra_data,
                },
            ],
        }


class ApprovedMailTemplate(MailTemplate):
    template_id = 5792978
    subject = "Get A Wash | You\'ve been approved!"


class CodeMailTemplate(MailTemplate):
    template_id = 5798048
    subject = 'Password reset code'


class DeniedMailTemplate(MailTemplate):
    template_id = 5771049
    subject = 'Get A Wash | Job was full!'


class SelectedWorkerTemplate(MailTemplate):
    template_id = 6150888
    subject = 'Get A Wash | A worker has been selected for your job!'


class TimeRegisteredTemplate(MailTemplate):
    template_id = 6095618
    subject = 'Get A Wash | A worker registered time for your job!'


class CancelledMailTemplate(MailTemplate):
    template_id = 5792996
    subject = 'Get A Wash | Your job was cancelled!'
