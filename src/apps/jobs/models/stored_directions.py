import datetime
import uuid

import pytz
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models.geo import Address
from apps.jobs.models.job_state import JobState


class StoredDirections(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    from_lat = models.IntegerField()
    from_lon = models.IntegerField()

    to_lat = models.IntegerField()
    to_lon = models.IntegerField()

    directions_response = models.TextField()

    created_at = models.DateTimeField(default=timezone.now)

    def check_expired(self):
        if self.created_at + datetime.timedelta(days=settings.GOOGLE_DIRECTIONS_EXPIRES_IN_DAYS) < timezone.now():
            self.delete()
            return True
        
        return False