from django.core.mail import send_mail
from mailjet_rest import Client
from apps.notifications.models.mail_template import MailTemplate
from django.contrib.auth import get_user_model

User = get_user_model()


class MailServiceManager:
    """
    Manager for managing mails
    """

    base_mail_address = 'hello@getawash.be'

    api_key = '7d678a5be4ccccd43fe63ff9a5bc8264'
    api_secret = '8f56591178b07bdd3d1f2fec0b08c285'

    @staticmethod
    def send_template(user: User, template: MailTemplate, data: dict):
        mailjet = Client(auth=(MailServiceManager.api_key, MailServiceManager.api_secret), version='v3.1')

        response = mailjet.send.create(
            data=template.to_data({"Email": user.email, "Name": "{} {}".format(user.first_name, user.last_name, )},
                                  extra_data=data), fail_silently=False, )

        if response.status_code == 200:
            return

        raise Exception(response.json(), )

    @staticmethod
    def send_mail(user: User, subject: str, message: str, ):
        """
        Send mail to user recipient
        """

        send_mail(
            subject,
            message,
            MailServiceManager.base_mail_address,
            [user.email],
            fail_silently=False,
        )
