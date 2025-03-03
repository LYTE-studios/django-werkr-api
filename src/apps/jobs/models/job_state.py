from django.db import models


class JobState(models.TextChoices):

    """
    This class defines the possible states for a job using Django's TextChoices class.
    
    The states include:
    - 'fulfilled': The job has been fulfilled.
    - 'pending': The job is still under review.
    - 'done': The job has been done.
    - 'cancelled': The job has been cancelled.

    Args:
    models (TextChoices): Inherits from Django's TextChoices to define the states as text choices.

    Returns:
    None
    """

    fulfilled = "fulfilled"

    pending = "pending"

    done = "done"

    cancelled = "cancelled"
