from django.urls import path

from .views import (
    NotificationView,
    NotificationReadView,
    UpdateFcmTokenView,
)

urlpatterns = [
    # Jobs
    path("notifications", NotificationView.as_view()),
    path("notifications/read-all", NotificationReadView.as_view()),
    path("users/fcm", UpdateFcmTokenView.as_view()),
]

