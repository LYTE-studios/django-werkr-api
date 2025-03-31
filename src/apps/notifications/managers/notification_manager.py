from apps.core.assumptions import WORKERS_GROUP_NAME, CMS_GROUP_NAME
from django.contrib.auth import get_user_model
from firebase_admin import messaging
from apps.core.decorators import async_task
User = get_user_model()
from asgiref.sync import sync_to_async

from apps.authentication.user_exceptions import UserNotFoundException
from apps.core.utils.formatters import FormattingUtil
from apps.notifications.models.mail_template import MailTemplate
from apps.notifications.models.notification import Notification
from apps.notifications.models.notification_status import NotificationStatus
from apps.core.models.settings import Settings


class NotificationManager:
    """
    Manager for managing notifications.
    """

    @staticmethod
    def notify_admin(title: str, description: str, send_mail=False):
        """
        Notify all admin users with a given title and description.

        Args:
            title (str): The title of the notification.
            description (str): The description of the notification.
            send_mail (bool): Whether to send an email notification. Defaults to False.
        """
        users = get_user_set(group_name=CMS_GROUP_NAME)

        notification = NotificationManager.create_notification(title, description, None)
        notification.is_global = True
        notification.save()

        for user in users:
            NotificationManager.assign_notification(user, notification, send_push=True, send_mail=send_mail)

    @staticmethod
    def create_notification_for_user(user: User, title: str, description: str, image_url, send_mail=False):
        """
        Create a new notification and assign it to a single user.

        Args:
            user (User): The user to assign the notification to.
            title (str): The title of the notification.
            description (str): The description of the notification.
            image_url (str): The URL of the image associated with the notification.
            send_mail (bool): Whether to send an email notification. Defaults to False.

        Returns:
            NotificationStatus: The status of the notification.
        """
        notification = NotificationManager.create_notification(title, description, image_url)
        notification_status = NotificationManager.assign_notification(user, notification, send_push=True,
                                                                      send_mail=send_mail)
        return notification_status

    @staticmethod
    def assign_notification(user: User, notification: Notification, send_push=True, send_mail=False):
        """
        Assign a notification to a user.

        Args:
            user (User): The user to assign the notification to.
            notification (Notification): The notification to assign.
            send_push (bool): Whether to send a push notification. Defaults to True.
            send_mail (bool): Whether to send an email notification. Defaults to False.

        Returns:
            NotificationStatus: The status of the notification.
        """
        notification_status = NotificationStatus(user=user, notification_id=notification.id)
        notification_status.save()

        if send_push and user.fcm_token is not None:
            NotificationManager.send_push_notification(user.fcm_token, notification)

        if send_mail:
            MailTemplate().send(recipients=[{'Email': user.email}], data={
                "title": notification.title,
                "description": notification.description,
            })

        return notification_status

    @staticmethod
    def create_notification(title: str, description: str, image_url):
        """
        Create a new notification.

        Args:
            title (str): The title of the notification.
            description (str): The description of the notification.
            image_url (str): The URL of the image associated with the notification.

        Returns:
            Notification: The created notification.
        """
        notification = Notification(title=title, description=description, pfp_url=image_url)
        notification.save()
        return notification

    @staticmethod
    def send_push_notification(token: str, notification: Notification):
        """
        Send a push notification to a specified FCM token.

        Args:
            token (str): The FCM token to send the notification to.
            notification (Notification): The notification to send.
        """
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.description,
                image=notification.pfp_url,
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default'),
                ),
            ),
            token=token,
        )
        
        try:
            messaging.send(message)
        except ValueError as e:
            raise e
        except Exception as e:
            pass


def get_user_set(group_name: str = WORKERS_GROUP_NAME, language: str = None):
    """
    Get the set of users in a specified group.

    Args:
        group_name (str): The name of the group. Defaults to WORKERS_GROUP_NAME.
        language (str): The language filter. Defaults to None.

    Returns:
        QuerySet: The set of users in the specified group.
    """
    try:
        group = FormattingUtil.to_group(group_name)
        users = group.user_set.all()
    except User.DoesNotExist:
        raise UserNotFoundException

    if language is not None:
        setting = Settings.objects.filter(language=language.lower())
        users = users.filter(settings_id__in=setting.values_list('id'))

    return users

def create_global_mail(title: str, description: str, user_id: str = None, group_name: str = WORKERS_GROUP_NAME,
                       language: str = None):
    """
    Send a mail to the specified group without saving it as a notification.

    Args:
        title (str): The title of the mail.
        description (str): The description of the mail.
        user_id (str): The ID of the user to send the mail to. Defaults to None.
        group_name (str): The name of the group. Defaults to WORKERS_GROUP_NAME.
        language (str): The language filter. Defaults to None.
    """
    if user_id is not None and user_id != '':
        try:
            user = User.objects.get(id=user_id)
            MailTemplate().send(recipients=[{'Email': user.email}], data={
                "title": title,
                "description": description,
            })
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = get_user_set(group_name, language)

    for user in users:
        if hasattr(user, 'worker_profile'):
            if not user.worker_profile.accepted:
                continue
        if user.archived:
            continue

        MailTemplate().send(recipients=[{'Email': user.email}], data={
            "title": title,
            "description": description,
        })

def send_lonely_push(title: str, description: str, user_id: str = None, group_name: str = WORKERS_GROUP_NAME,
                     language: str = None) -> None:
    """
    Send a push notification without saving it to the notification center.

    Args:
        title (str): The title of the push notification.
        description (str): The description of the push notification.
        user_id (str): The ID of the user to send the notification to. Defaults to None.
        group_name (str): The name of the group. Defaults to WORKERS_GROUP_NAME.
        language (str): The language filter. Defaults to None.
    """
    if user_id is not None and user_id != '':
        try:
            user = User.objects.get(id=user_id)
            NotificationManager.send_push_notification(user.fcm_token,
                                                       Notification(title=title, description=description))
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = get_user_set(group_name, language)

    for user in users:
        if not user.accepted:
            continue
        if user.archived:
            continue

        NotificationManager.send_push_notification(user.fcm_token, Notification(title=title, description=description))

@async_task
async def create_global_notification(title: str, description: str, image_url: str = None, user_id: str = None,
                               send_push: bool = False, group_name: str = WORKERS_GROUP_NAME,
                               language: str = None) -> None:
    """
    Create a global notification for all users in a group.

    Args:
        title (str): The title of the notification.
        description (str): The description of the notification.
        image_url (str): The URL of the image associated with the notification. Defaults to None.
        user_id (str): The ID of the user to send the notification to. Defaults to None.
        send_push (bool): Whether to send a push notification. Defaults to False.
        group_name (str): The name of the group. Defaults to WORKERS_GROUP_NAME.
        language (str): The language filter. Defaults to None.
    """

    def send():
        notification = NotificationManager.create_notification(title, description, image_url)

        if user_id is not None and user_id != '':
            try:
                user = User.objects.get(id=user_id)
                NotificationManager.assign_notification(user, notification, send_push=send_push)
                return
            except User.DoesNotExist:
                raise Exception('User does not exist')

        users = get_user_set(group_name, language)

        for user in users:
            if not user.is_accepted():
                continue
            if user.archived:
                continue

            NotificationManager.assign_notification(user, notification, send_push=send_push)

    sync_to_async(send)()