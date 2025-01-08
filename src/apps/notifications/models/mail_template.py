from mailjet_rest import Client
from django.conf import settings
import asyncio

class MailTemplate:

    template_id: int = 5794325
    subject: str = 'Get A Wash | New message'

    async def _send_task(self, recipients: list[str], data: dict, loop=None):
        """Async task to send emails asynchronously"""

        try: 
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

            return response.status_code == 200
        
        except Exception as e:
            # Log the error but don't raise it
            print(f"Error sending email: {str(e)}")
            return False
        
    from apps.core.decorators import ensure_event_loop

    @ensure_event_loop
    def send(self, recipients: list[str], data: dict):
        """Sends email synchronously"""
        asyncio.create_task(self._send_task(recipients=recipients, data=data),)

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
    subject = 'Get A Wash | A washer has been selected for your job!'


class TimeRegisteredTemplate(MailTemplate):
    template_id = 6095618
    subject = 'Get A Wash | A washer registered time for your job!'


class CancelledMailTemplate(MailTemplate):
    template_id = 5792996
    subject = 'Get A Wash | Your job was cancelled!'
