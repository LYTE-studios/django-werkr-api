from http import HTTPStatus
from django.http import HttpRequest
from django.shortcuts import render
from rest_framework.response import Response

from apps.authentication.views import JWTBaseAuthView
from apps.core.assumptions import *
from apps.notifications.models.notification_status import NotificationStatus
from apps.core.utils.wire_names import *
from apps.core.utils.formatters import FormattingUtil
from apps.core.model_exceptions import DeserializationException
from apps.notifications.managers.notification_manager import create_global_mail, create_global_notification
from apps.notifications.models.notification import Notification

# Create your views here.

class NotificationReadView(JWTBaseAuthView):
    """
    [CMS, Washer]

    GET | POST

    A view for crud on notifications
    """

    groups = [
        WORKERS_GROUP_NAME,
        CMS_GROUP_NAME,
    ]

    def put(self, request: HttpRequest):
        user = self.user

        try:
            # Fetch all notification statuses for the user and mark them as seen
            NotificationStatus.objects.filter(user=user).update(seen=True)

            # Return a successful response indicating all notifications have been marked as read
            return Response(
                {"message": "All notifications marked as read."}, status=HTTPStatus.OK
            )

        except Exception as e:
            # Return an error response if something goes wrong
            return Response({k_message: str(e)}, status=HTTPStatus.BAD_REQUEST)
        

class NotificationView(JWTBaseAuthView):
    """
    [CMS, Washer]

    GET | POST

    A view for crud on notifications
    """

    groups = [
        WORKERS_GROUP_NAME,
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest):
        data = []

        # Fetch notifications specific to the user
        user_notifications = (
            NotificationStatus.objects.filter(
                user=self.user,
                notification__is_global=self.group.name == CMS_GROUP_NAME,
            )
            .order_by(
                "-notification__sent",
            )
            .prefetch_related("notification")[:50]
        )

        # Add user-specific notifications to data
        for notification_status in user_notifications:
            data.append(notification_status.to_model_view())

        return Response({k_notifications: data})

    def post(self, request: HttpRequest):
        formatter = FormattingUtil(data=request.data)

        try:
            title = formatter.get_value(k_title, required=True)
            description = formatter.get_value(k_description, required=True)
            user_id = formatter.get_value(k_user_id, required=False)
            send_push = formatter.get_bool(k_send_push, required=False) or False
            send_mail = formatter.get_bool(k_send_mail, required=False) or False
            language = formatter.get_value(k_language, required=False)

        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        create_global_notification(
            title=title,
            description=description,
            send_push=send_push,
            send_mail=send_mail,
            user_id=user_id,
            language=language,
        )

        return Response(status=HTTPStatus.OK)

    def put(self, request: HttpRequest):
        formatter = FormattingUtil(data=request.data)

        try:
            # Retrieve the notification ID from the request
            notification_id = formatter.get_value(k_id, required=True)

            seen = formatter.get_bool(k_seen, required=False)
            archived = formatter.get_bool(k_archived, required=False)

        except DeserializationException as e:
            # Return an error response if an exception occurs
            return Response({k_message: str(e)}, status=HTTPStatus.BAD_REQUEST)

        try:
            notification = Notification.objects.get(id=notification_id)
            notification_status = NotificationStatus.objects.get(
                notification=notification,
                user_id=self.user.id,
            )
        except Notification.DoesNotExist:
            return Response({k_id: notification_id}, status=HTTPStatus.NOT_FOUND)
        except NotificationStatus.DoesNotExist:
            return Response({k_id: notification_id}, status=HTTPStatus.NOT_FOUND)

        notification_status.seen = seen or notification_status.seen
        notification_status.archived = archived or notification_status.archived

        # Save changes to the database
        notification_status.save()

        # Return a successful response with the notification ID
        return Response({k_id: str(notification.id)}, status=HTTPStatus.OK)



class UpdateFcmTokenView(JWTBaseAuthView):
    """
    [CMS]

    POST

    View for updating base user details.
    """

    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest, *args, **kwargs):

        formatter = FormattingUtil(data=request.data)

        try:
            # Get the user id
            user = self.user
            fcm_token = formatter.get_value(k_fcm_token, required=True)
            if fcm_token:
                user.fcm_token = fcm_token
            else:
                return Response(
                    {k_message: "FCM token not provided"}, status=HTTPStatus.BAD_REQUEST
                )

        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response(
                {k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

        # Save the user
        user.save()

        # Return the user's id
        return Response({k_user_id: user.id})
