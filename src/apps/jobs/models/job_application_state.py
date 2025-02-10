from django.db import models


class JobApplicationState(models.TextChoices):

    approved = "approved"

    pending = "pending"

    rejected = "rejected"
