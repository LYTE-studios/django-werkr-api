import datetime
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class StoredDirections(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    from_lat = models.FloatField()
    from_lon = models.FloatField()

    to_lat = models.FloatField()
    to_lon = models.FloatField()

    directions_response = models.TextField()

    created_at = models.DateTimeField(default=timezone.now)

    def check_expired(self):
        if (
            self.created_at
            + datetime.timedelta(days=settings.GOOGLE_DIRECTIONS_EXPIRES_IN_DAYS)
            < timezone.now()
        ):
            self.delete()
            return True

        return False
