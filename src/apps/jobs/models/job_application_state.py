from django.db import models


class JobApplicationState(models.TextChoices):

    """
    This class defines the possible states for a job application using Django's TextChoices class.
    
    The states include:
    - 'approved': The job application has been approved.
    - 'pending': The job application is still under review.
    - 'rejected': The job application has been rejected.

    Args:
    models (TextChoices): Inherits from Django's TextChoices to define the states as text choices.

    Returns:
    None
    """

    approved = "approved"

    pending = "pending"

    rejected = "rejected"

