import random
import secrets
from datetime import timedelta

from django.utils import timezone

from apps.authentication.models.pass_reset import PassResetCode
from apps.notifications.managers.mail_service_manager import MailServiceManager
from apps.notifications.models.mail_template import CodeMailTemplate


def generate_code():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


class CustomPasswordResetUtil:
    def send_reset_code(self, user):
        code = generate_code()
        pass_code = PassResetCode(
            user=user,
            code=code
        )

        pass_code.save()

        MailServiceManager.send_template(user, CodeMailTemplate(5798048, 'Password reset code'), {
            "code": code,
        })

    def verify_code(self, user, code):
        pass_code = PassResetCode.objects.filter(user=user, code=code, used=False).first()
        if pass_code and pass_code.generated_at > timezone.now() - timezone.timedelta(minutes=5):
            pass_code.used = True
            pass_code.save()
            return True
        else:
            return False

    def create_temporary_token_for_user(self, user, code):
        # Generate a secure, random token
        token = secrets.token_urlsafe()

        # Set the token and its expiry time (e.g., 30 minutes from now)
        pass_code = PassResetCode.objects.filter(user=user, code=code, used=True).first()
        pass_code.reset_password_token = token
        pass_code.token_expiry_time = timezone.now() + timedelta(minutes=10)
        pass_code.save()

        return token

    def get_user_by_token_and_code(self, token, code):
        pass_code = PassResetCode.objects.filter(reset_password_token=token, code=code, used=True).first()
        if pass_code and pass_code.token_expiry_time > timezone.now():
            return pass_code.user
        else:
            return None

    def reset_password(self, user, password):
        user.set_password(password)
        user.save()
        pass_code = PassResetCode.objects.filter(user=user, used=True).first()
        pass_code.delete()
