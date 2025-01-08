from django.db import models

from api.settings import AUTH_USER_MODEL
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .notification import Notification


class NotificationStatus(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)

    notification = models.ForeignKey(Notification, on_delete=models.PROTECT, null=True)

    seen = models.BooleanField(default=False)

    archived = models.BooleanField(default=False)

    def to_model_view(self):
        return {
            k_id: self.notification.id,
            k_title: self.notification.title,
            k_description: self.notification.description,
            k_profile_picture: self.notification.pfp_url,
            k_sent: FormattingUtil.to_timestamp(self.notification.sent),
            k_seen: FormattingUtil.to_bool(self.seen),
            k_archived: FormattingUtil.to_bool(self.archived),
        }
