from django.db import models

from apps.core.utils.wire_names import *
from .application import JobApplication


class Dimona(models.Model):

    id = models.CharField(primary_key=True, null=False, max_length=32)

    application = models.ForeignKey(
        JobApplication, on_delete=models.PROTECT, default=None
    )

    success = models.BooleanField(null=True)

    reason = models.CharField(max_length=256, null=True)

    created = models.DateTimeField(null=True)

    def to_model_view(self):
        return {
            k_id: self.id,
            k_application: self.application.to_model_view(),
            k_success: self.success,
            k_description: self.reason,
            k_created_at: self.created,
        }
