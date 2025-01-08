import uuid

from django.db import models
from django.utils import timezone


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=128, null=True)

    description = models.CharField(max_length=256, null=True)

    created = models.DateTimeField(default=timezone.now)

    sent = models.DateTimeField(default=timezone.now)

    is_global = models.BooleanField(default=False)

    has_mail = models.BooleanField(default=False)

    pfp_url = models.CharField(max_length=128, null=True)
