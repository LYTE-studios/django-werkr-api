from django.db import models


class JobState(models.TextChoices):

    fulfilled = "fulfilled"

    pending = "pending"

    done = "done"

    cancelled = "cancelled"
