from apps.core.assumptions import WORKERS_GROUP_NAME, CMS_GROUP_NAME
from django.contrib.auth import get_user_model
from firebase_admin import messaging
from apps.core.decorators import async_task
User = get_user_model()
from asgiref.sync import sync_to_async
import logging
logger = logging.getLogger(__name__)

from apps.authentication.models import WorkerProfile
from apps.notifications.models.mail_template import MailTemplate
from apps.notifications.models.notification import Notification
from apps.notifications.models.notification_status import NotificationStatus
from apps.core.models.settings import Settings
from django.contrib.auth.models import Group



class NotificationManager:
    """
    Manager for managing notifications.
    """

    @staticmethod
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
            group = Group.objects.get(name=group_name)
            users = group.user_set.all()

            if language is not None:
                setting =  Settings.objects.filter(language=language.lower())
                setting_ids = setting.values_list('id')
                users = users.filter(settings_id__in=setting_ids)

            return users
        except Exception as e:
            logger.error(f"Error getting user set: {str(e)}")
            raise e

    @staticmethod
    def notify_admin(title: str, description: str, send_mail=False):
        """
        Notify all admin users with a given title and description.

        Args:
            title (str): The title of the notification.
            description (str): The description of the notification.
            send_mail (bool): Whether to send an email notification. Defaults to False.
        """
        users =  NotificationManager.get_user_set(group_name=CMS_GROUP_NAME)
        notification = Notification.objects.create(title=title, description=description)
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
        notification = Notification.objects.create(title=title, description=description, pfp_url=image_url)
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

        # Create and save notification status
        notification_status = NotificationStatus.objects.create(user=user, notification_id=notification.id)

        if send_push and user.fcm_token is not None:
            try:
                NotificationManager.send_push_notification(user.fcm_token, notification)
            except messaging.ApiCallError as e:
                logger.warning(f"Firebase API error for user {user.id}: {e.code} - {e.message}")
                # Don't raise for FCM errors - continue with other notifications
                pass
            except Exception as e:
                logger.error(f"Error sending push notification to user {user.id}: {str(e)}")
                # Don't raise for push notification errors - continue with other notifications
                pass

        if send_mail:
            try:
                MailTemplate().send([{'Email': user.email}], {
                        "title": notification.title,
                        "description": notification.description,
                    })
            except Exception as e:
                logger.error(f"Error sending mail to user {user.id}: {str(e)}")
                # Don't raise for email errors - continue with other notifications
                pass

        return notification_status

    @staticmethod
    def send_push_notification(token: str, notification: Notification):
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
        
            response = messaging.send(message)

            if response:
                logger.info(f"Successfully sent message: {response}")
            else: 
                logger.error(f"Error sending message: {response}")
                raise Exception(f"Error sending message: {response}")
                            
        except Exception as e:
            error_message = f"Error sending push notification: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

def create_global_notification(title: str, description: str, image_url: str = None, user_id: str = None,
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

    # Create notification
    notification = Notification.objects.create(title=title, description=description, pfp_url=image_url)

    if user_id:
        try:
            user = User.objects.get(id=user_id)
            
        except User.DoesNotExist:
            raise Exception('User does not exist')
        except Exception as e:
            logger.error(f"Error setting notification: {str(e)}")
            raise e

    users = NotificationManager.get_user_set(group_name, language)

    logger.info(f"Sending notification to {users.count()} users")

    for user in users:
        try:
            logger.info(f"Sending notification to {user.id}")

            if not hasattr(user, 'is_accepted') or not user.is_accepted():
                logger.info(f"Skipping user {user.id} - not accepted")
                continue

            NotificationManager.assign_notification(user, notification, send_push=send_push, send_mail=send_mail)
        except Exception as e:
            logger.error(f"Error processing notification for user {user.id}: {str(e)}")
            continue

