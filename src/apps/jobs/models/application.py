import uuid

from django.conf import settings
from django.db import models

from apps.core.models.geo import Address
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .job import Job
from .job_application_state import JobApplicationState
from apps.jobs.utils.job_util import JobUtil


class JobApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    job = models.ForeignKey(Job, on_delete=models.PROTECT)

    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    address = models.ForeignKey(Address, on_delete=models.CASCADE)

    application_state = models.CharField(max_length=64, choices=JobApplicationState.choices,
                                         default=JobApplicationState.pending)

    distance = models.FloatField(null=True)

    no_travel_cost = models.BooleanField(default=True)

    created_at = models.DateTimeField()

    modified_at = models.DateTimeField()

    note = models.CharField(max_length=256, null=True)

    def get_contract_upload_path(instance, file_name):
        return 'contracts/{}/{}'.format( instance.worker.id, file_name)

    contract = models.FileField(upload_to=get_contract_upload_path, null=True)

    def to_model_view(self):
        url = None

        try:
            url = self.contract.url
        except Exception:
            pass

        return {
            k_id: self.id,
            k_job: JobUtil.to_model_view(self.job),
            k_start_time: FormattingUtil.to_timestamp(self.job.start_time),
            k_end_time: FormattingUtil.to_timestamp(self.job.end_time),
            k_max_workers: self.job.max_workers,
            k_selected_workers: self.job.selected_workers,
            k_application_start_time: FormattingUtil.to_timestamp(self.job.application_start_time),
            k_application_end_time: FormattingUtil.to_timestamp(self.job.application_end_time),
            k_worker: self.worker.to_worker_view(),
            k_address: self.address.to_model_view(),
            k_state: self.application_state,
            k_distance: self.distance,
            k_no_travel_cost: self.no_travel_cost,
            k_created_at: FormattingUtil.to_timestamp(self.created_at),
            k_note: self.note,
            k_contract: url,
        }
