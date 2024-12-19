from celery import shared_task
from firebase_admin import messaging

from apps.core.assumptions import WASHERS_GROUP_NAME, CMS_GROUP_NAME
from django.contrib.auth import get_user_model

User = get_user_model()
from apps.authentication.user_exceptions import UserNotFoundException
from apps.core.utils.formatters import FormattingUtil
from apps.notifications.models.mail_template import MailTemplate
from apps.notifications.models.notification import Notification
from apps.notifications.models.notification_status import NotificationStatus
from apps.core.models.settings import Settings


class NotificationManager:
    """
    Manager for managing notifications
    """

    @staticmethod
    def notify_admin(title: str, description: str, send_mail=False):

        users = get_user_set(group_name=CMS_GROUP_NAME)

        notification = NotificationManager.create_notification(title, description, None)

        notification.is_global = True

        notification.save()

        for user in users:
            NotificationManager.assign_notification(user, notification, send_push=True,
                                                                        send_mail=send_mail, )


    @staticmethod
    def create_notification_for_user(user: User, title: str, description: str, image_url, send_mail=False, ):
        """
        Create a new notification an assign it to 1 user
        """

        notification = NotificationManager.create_notification(title, description, image_url)

        notification_status = NotificationManager.assign_notification(user, notification, send_push=True,
                                                                      send_mail=send_mail, )

        return notification_status

    @staticmethod
    def assign_notification(user: User, notification: Notification, send_push=True, send_mail=False, ):
        """
        Private function to assign users to a notification
        """

        # Create notification
        notification_status = NotificationStatus(user=user, notification_id=notification.id)
        notification_status.save()

        if send_push == True and user.fcm_token is not None:
            NotificationManager.send_push_notification(user.fcm_token, notification)

        if send_mail:
            MailTemplate.send([user.email], data={
                "title": notification.title,
                "description": notification.description,
            }, )

        # Return the status
        return notification_status

    @staticmethod
    def create_notification(title: str, description: str, image_url, ):
        """
        Private function to create a new notification using a title and description
        """
        # Create notification
        notification = Notification(title=title, description=description, pfp_url=image_url)

        # Save the notification
        notification.save()

        # Return
        return notification

    @staticmethod
    def send_push_notification(token: str, notification: Notification):
        """
        Send notification to the specified fcm token
        """

        # Construct the message
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.description,
                image=notification.pfp_url,
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default',),
                ),
            ),
            token=token,
        )

        try:
            # Send the message
            messaging.send(message)
        except Exception:
            pass


def get_user_set(group_name: str = WASHERS_GROUP_NAME, language: str=None):
    # Get the users in specified group
    try:
        group = FormattingUtil.to_group(group_name)

        users = group.user_set.all()
    except User.DoesNotExist:
        raise UserNotFoundException

    if language is not None:
        setting = Settings.objects.filter(language=language.lower())

        users = users.filter(settings_id__in=setting.values_list('id'))

    return users


@shared_task
def create_global_mail(title: str, description: str, user_id: str = None, group_name: str = WASHERS_GROUP_NAME, language: str=None):
    """
    Sends a mail to the specified group

    DOES NOT SAVE THE MESSAGE AS A NOTIFICATION
    """

    if user_id is not None and user_id != '':
        try:
            user = User.objects.get(id=user_id)

            MailTemplate.send([user.email], data={
                    "title": title,
                    "description": description,
                }, )
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = get_user_set(group_name, language)

    for user in users:
        if not user.accepted:
            continue
        if user.archived:
            continue
        MailTemplate.send([user.email], data={
                "title": title,
                "description": description,
            }, )

@shared_task
def send_lonely_push(title: str, description: str, user_id: str = None, group_name: str = WASHERS_GROUP_NAME, language: str = None,) -> None:
    """
    Sends a push notification without saving it to the notification center
    """

    if user_id is not None and user_id != '':
        try:
            user = User.objects.get(id=user_id)

            NotificationManager.send_push_notification(user.fcm_token, Notification(title=title, description=description,),)
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = get_user_set(group_name, language)

    for user in users:
        if not user.accepted:
            continue
        if user.archived:
            continue

        NotificationManager.send_push_notification(user.fcm_token, Notification(title=title, description=description,),)

@shared_task
def create_global_notification(title: str, description: str, image_url: str = None, user_id: str = None, send_push: bool = False,
                               group_name: str = WASHERS_GROUP_NAME, language: str = None) -> None:
    """
    Create a global notification for all users in a group.

    By default, the group name is set to the workers group
    """

    notification = NotificationManager.create_notification(title, description, image_url, )

    if user_id is not None and user_id != '':
        try:
            user = User.objects.get(id=user_id)

            NotificationManager.assign_notification(user, notification, send_push=send_push)
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = get_user_set(group_name, language)

    for user in users:
        if not user.accepted:
            continue
        if user.archived:
            continue

        NotificationManager.assign_notification(user, notification, send_push=send_push)
