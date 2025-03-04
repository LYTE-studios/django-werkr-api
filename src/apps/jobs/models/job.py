import datetime
import uuid

import pytz
from apps.core.models.geo import Address
from .job_state import JobState
from django.conf import settings
from django.db import models
from django.utils import timezone


class Job(models.Model):

    """
    This class manages operations related to jobs, such as determining if the job is currently
    visible.
    This model is associated with a specific id, customer, title, description, address,
    keeping track of its state and the time within the application start and end time.
    
    """
     
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, default=None)

    title = models.CharField(max_length=64, default='')

    description = models.CharField(max_length=256, default='')

    address = models.ForeignKey(Address, on_delete=models.CASCADE)

    job_state = models.CharField(max_length=64, choices=JobState.choices, default=JobState.pending)

    start_time = models.DateTimeField(default=timezone.now)

    end_time = models.DateTimeField(null=True, blank=True)

    application_start_time = models.DateTimeField(null=True, blank=True, default=timezone.now)

    application_end_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    modified_at = models.DateTimeField(null=True, blank=True)

    is_draft = models.BooleanField(default=False)

    archived = models.BooleanField(default=False)

    max_workers = models.IntegerField(null=True, blank=True)

    selected_workers = models.IntegerField(null=True, blank=True)

    def is_visible(self):

        """
        Determines if the job is currently visible based on its application period, 
        draft status, archive status, and worker availability.

        A job is considered visible if:
        - The current time is within the application start and end time.
        - The job is not in draft mode.
        - The job is not archived.
        - The number of selected workers is less than the maximum allowed.

        Args:
        self (Job): An instance of the Job model.
  
        Returns:
        bool: True if the job is visible, otherwise False.
        """

        start = timezone.make_aware(self.application_start_time)
        end = timezone.make_aware(self.application_end_time)

        time_window_check = start <= timezone.now() <= end

        draft_check = not self.is_draft

        archived_check = not self.archived

        workers_check = self.selected_workers < self.max_workers

        return time_window_check and draft_check and archived_check and workers_check
