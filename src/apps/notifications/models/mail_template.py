from mailjet_rest import Client
from django.conf import settings
import asyncio

class MailTemplate:

    template_id: int = 6868496
    subject: str = 'Werkr | New message'

    def send(self, recipients: list[str], data: dict):

        mailjet = Client(auth=(settings.MAILJET_API_KEY, settings.MAILJET_API_SECRET), version='v3.1')

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

        if response.status_code != 200:
            raise Exception("Error sending mail: " + response.text)

class ApprovedMailTemplate(MailTemplate):
    template_id = 6867411
    subject = "Werkr | You\'ve been approved!"

class CodeMailTemplate(MailTemplate):
    template_id = 6867284
    subject = 'Werkr | Password reset code'


class DeniedMailTemplate(MailTemplate):
    template_id = 6857054
    subject = 'Werkr | Job was full!'


class SelectedWorkerTemplate(MailTemplate):
    template_id = 6868426
    subject = 'Werkr | A washer has been selected for your job!'


class TimeRegisteredTemplate(MailTemplate):
    template_id = 6868519
    subject = 'Werkr | A washer registered time for your job!'


class CancelledMailTemplate(MailTemplate):
    template_id = 6867436
    subject = 'Werkr | Your job was cancelled!'
