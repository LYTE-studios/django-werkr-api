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
    async def get_user_set(group_name: str = WORKERS_GROUP_NAME, language: str = None):
        """
        Get the set of users in a specified group.

        Args:
            group_name (str): The name of the group. Defaults to WORKERS_GROUP_NAME.
            language (str): The language filter. Defaults to None.

        Returns:
            QuerySet: The set of users in the specified group.
        """
        try:
            group = await sync_to_async(Group.objects.get)(name=group_name)
            users = await sync_to_async(group.user_set.all)()

            if language is not None:
                setting =  await sync_to_async(Settings.objects.filter)(language=language.lower())
                setting_ids = await sync_to_async(setting.values_list)('id')
                users = await sync_to_async(users.filter)(settings_id__in=setting_ids)

            return await sync_to_async(users.values)()
        except Exception as e:
            logger.error(f"Error getting user set: {str(e)}")
            raise e

    @staticmethod
    async def notify_admin(title: str, description: str, send_mail=False):
        """
        Notify all admin users with a given title and description.

        Args:
            title (str): The title of the notification.
            description (str): The description of the notification.
            send_mail (bool): Whether to send an email notification. Defaults to False.
        """
        save_notification = sync_to_async(lambda x: x.save())

        users = await NotificationManager.get_user_set(group_name=CMS_GROUP_NAME)
        notification = await sync_to_async(Notification.objects.create)(title=title, description=description)
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
        notification = await sync_to_async(Notification.objects.create)(title=title, description=description, pfp_url=image_url)
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

        # Create and save notification status
        notification_status = await sync_to_async(NotificationStatus.objects.create)(user=user, notification_id=notification.id)

        if send_push and user.fcm_token is not None:
            try:
                await NotificationManager.send_push_notification(user.fcm_token, notification)
            except Exception as e: 
                logger.error(f"Error sending push notification to user {user.id}: {str(e)}")
                raise e

        if send_mail:
            try:
                MailTemplate().send([{'Email': user.email}], {
                        "title": notification.title,
                        "description": notification.description,
                    })
            except Exception as e: 
                logger.error(f"Error sending mail to user {user.id}: {str(e)}")
                raise e 

        return notification_status

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
            logger.info(f"Successfully sent message: {response}")
            
        except messaging.ApiCallError as firebase_error:
            error_message = f"Firebase API error: {firebase_error.code} - {firebase_error.message}"
            logger.error(error_message)
            raise Exception(error_message)
            
        except Exception as e:
            error_message = f"Error sending push notification: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

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

        # Create notification
        notification = await sync_to_async(Notification.objects.create)(title=title, description=description, pfp_url=image_url)

        async def assign(user: User):
            try:
                await NotificationManager.assign_notification(user, notification, send_push=send_push, send_mail=send_mail)
            except Exception as e:
                logger.error(f"Error assigning notification to user {user.id}: {str(e)}")
                raise e 

        if user_id:
            try:
                user = await sync_to_async(User.objects.get)(id=user_id)
                await assign(user)
                return
            except User.DoesNotExist:
                raise Exception('User does not exist')
            except Exception as e:
                logger.error(f"Error setting notification: {str(e)}")
                raise e

        users = await NotificationManager.get_user_set(group_name, language)

        logger.info(f"Sending notification to {len(users)} users")

        for user in users:
            logger.info(f"Sending notification to {user.id}")

            try:
                if hasattr(user, 'worker_profile'):
                    worker_profile = await sync_to_async(WorkerProfile.objects.get)(user=user)
                    if not worker_profile.accepted:
                        continue
                if user.archived:
                    continue
            except Exception as e: 
                logger.error(f"Error checking user status: {str(e)}")
                raise e 
    
            await assign(user)

    # No need to wrap in sync_to_async since send() is already async
    await send()