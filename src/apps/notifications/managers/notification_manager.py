from apps.core.assumptions import WORKERS_GROUP_NAME, CMS_GROUP_NAME
from django.contrib.auth import get_user_model
from firebase_admin import messaging
from apps.core.decorators import async_task
User = get_user_model()
from asgiref.sync import sync_to_async

class ThirdPartyAuthError(Exception):
    """Raised when there's an authentication error with a third-party service."""
    pass

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
    async def notify_admin(title: str, description: str, send_mail=False):
        """
        Notify all admin users with a given title and description.

        Args:
            title (str): The title of the notification.
            description (str): The description of the notification.
            send_mail (bool): Whether to send an email notification. Defaults to False.
        """
        get_users = sync_to_async(get_user_set)
        save_notification = sync_to_async(lambda x: x.save())

        users = await get_users(group_name=CMS_GROUP_NAME)
        notification = await NotificationManager.create_notification(title, description, None)
        notification.is_global = True
        await save_notification(notification)

        for user in users:
            await NotificationManager.assign_notification(user, notification, send_push=True, send_mail=send_mail)

    @staticmethod
    async def create_notification_for_user(user: User, title: str, description: str, image_url, send_mail=False):
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
        notification = await NotificationManager.create_notification(title, description, image_url)
        notification_status = await NotificationManager.assign_notification(user, notification, send_push=True,
                                                                      send_mail=send_mail)
        return notification_status

    @staticmethod
    async def assign_notification(user: User, notification: Notification, send_push=True, send_mail=False):
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
        # Wrap database operations in sync_to_async
        save_status = sync_to_async(lambda x: x.save())
        send_mail_template = sync_to_async(lambda x: MailTemplate().send(**x))

        # Create and save notification status
        notification_status = NotificationStatus(user=user, notification_id=notification.id)
        await save_status(notification_status)

        if send_push and user.fcm_token is not None:
            await NotificationManager.send_push_notification(user.fcm_token, notification)

        if send_mail:
            mail_args = {
                'recipients': [{'Email': user.email}],
                'data': {
                    "title": notification.title,
                    "description": notification.description,
                }
            }
            await send_mail_template(mail_args)

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
    async def send_push_notification(token: str, notification: Notification):
        """
        Send a push notification to a specified FCM token.

        Args:
            token (str): The FCM token to send the notification to.
            notification (Notification): The notification to send.

        Raises:
            ThirdPartyAuthError: If there's an authentication error with FCM/APNS
            Exception: For other errors during notification sending
        """
        try:
            # Configure APNS with more detailed settings
            apns_config = messaging.APNSConfig(
                headers={
                    'apns-priority': '10'  # High priority
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=notification.title,
                            body=notification.description
                        ),
                        sound='default',
                        badge=1
                    ),
                ),
            )

            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.description,
                    image=notification.pfp_url,
                ),
                apns=apns_config,
                token=token,
            )
        
            # Wrap Firebase messaging send in sync_to_async
            send_message = sync_to_async(messaging.send)
            response = await send_message(message)
            print(f"Successfully sent message: {response}")
            
        except messaging.ApiCallError as firebase_error:
            error_message = f"Firebase API error: {firebase_error.code} - {firebase_error.message}"
            print(error_message)
            if 'authentication' in str(firebase_error).lower():
                raise ThirdPartyAuthError(error_message)
            raise Exception(error_message)
            
        except Exception as e:
            error_message = f"Error sending push notification: {str(e)}"
            print(error_message)
            raise Exception(error_message)


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

async def create_global_mail(title: str, description: str, user_id: str = None, group_name: str = WORKERS_GROUP_NAME,
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
    get_user = sync_to_async(User.objects.get)
    get_users = sync_to_async(get_user_set)
    send_mail = sync_to_async(lambda x: MailTemplate().send(**x))
    has_worker_profile = sync_to_async(lambda u: hasattr(u, 'worker_profile'))
    is_worker_accepted = sync_to_async(lambda u: u.worker_profile.accepted)

    if user_id is not None and user_id != '':
        try:
            user = await get_user(id=user_id)
            mail_args = {
                'recipients': [{'Email': user.email}],
                'data': {
                    "title": title,
                    "description": description,
                }
            }
            await send_mail(mail_args)
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = await get_users(group_name, language)

    for user in users:
        if await has_worker_profile(user):
            if not await is_worker_accepted(user):
                continue
        if user.archived:
            continue

        mail_args = {
            'recipients': [{'Email': user.email}],
            'data': {
                "title": title,
                "description": description,
            }
        }
        await send_mail(mail_args)

async def send_lonely_push(title: str, description: str, user_id: str = None, group_name: str = WORKERS_GROUP_NAME,
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
    get_user = sync_to_async(User.objects.get)
    get_users = sync_to_async(get_user_set)
    is_accepted = sync_to_async(lambda u: u.accepted)

    if user_id is not None and user_id != '':
        try:
            user = await get_user(id=user_id)
            await NotificationManager.send_push_notification(user.fcm_token,
                                                        Notification(title=title, description=description))
            return
        except User.DoesNotExist:
            raise Exception('User does not exist')

    users = await get_users(group_name, language)

    for user in users:
        if not await is_accepted(user):
            continue
        if user.archived:
            continue

        await NotificationManager.send_push_notification(user.fcm_token, Notification(title=title, description=description))

@async_task
async def create_global_notification(title: str, description: str, image_url: str = None, user_id: str = None,
                               send_push: bool = False, group_name: str = WORKERS_GROUP_NAME, send_mail: bool = False,
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

    async def send():
        # Wrap database operations in sync_to_async
        create_notification = sync_to_async(NotificationManager.create_notification)
        get_user = sync_to_async(User.objects.get)
        get_users = sync_to_async(get_user_set)

        # Create notification
        notification = await create_notification(title, description, image_url)

        async def assign(user: User):
            await NotificationManager.assign_notification(user, notification, send_push=send_push, send_mail=send_mail)

        if user_id is not None and user_id != '':
            try:
                user = await get_user(id=user_id)
                await assign(user)
                return
            except User.DoesNotExist:
                raise Exception('User does not exist')

        users = await get_users(group_name, language)

        for user in users:
            if not await sync_to_async(user.is_accepted)():
                continue
            if user.archived:
                continue

            await assign(user)

    # No need to wrap in sync_to_async since send() is already async
    await send()