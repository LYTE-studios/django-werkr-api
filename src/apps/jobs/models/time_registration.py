import uuid

from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.models.job import Job
from apps.authentication.utils.media_util import MediaUtil
from apps.authentication.utils.worker_util import WorkerUtil


# # Define a standalone function for generating upload paths
# def get_upload_path(instance, filename):
#     # Determine the folder based on the type of signature
#     folder = 'worker' if 'worker' in filename else 'customer'
#     # Return the formatted upload path
#     return f'signatures/{instance.id}/{folder}/{filename}'

class TimeRegistration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name='worked_times')
    worker = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    break_time = models.TimeField(null=True)

    def get_upload_path(instance, filename):
        # Determine the folder based on the type of signature
        folder = 'worker' if 'worker' in filename else 'customer'
        # Return the formatted upload path
        return f'signatures/{instance.id}/{folder}/{filename}'

    # Use the named function for the upload_to argument
    worker_signature = models.ImageField(upload_to=get_upload_path, null=True, blank=True)
    customer_signature = models.ImageField(upload_to=get_upload_path, null=True, blank=True)

    def to_model_view(self):
        data = {
            k_id: self.id,
            k_start_time: FormattingUtil.to_timestamp(self.start_time),
            k_end_time: FormattingUtil.to_timestamp(self.end_time),
            k_break_time: FormattingUtil.to_timestamp(self.break_time),
            k_worker_signature:  MediaUtil.to_media_url(self.worker_signature.url) if self.worker_signature else None,
            k_customer_signature: MediaUtil.to_media_url(self.customer_signature.url) if self.customer_signature else None,
            k_worker: WorkerUtil.to_worker_view(self.worker) if self.worker else None,
        }

        return data
