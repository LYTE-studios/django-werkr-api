import uuid

from django.db import models
from django.utils import timezone

from core.features.base.util.formatting_util import FormattingUtil
from core.features.base.util.wire_names import *
from core.features.profile.utils.media_util import MediaUtil

class ExportFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=128)

    file_name = models.CharField(max_length=128)

    description = models.CharField(max_length=256, null=True)

    created = models.DateTimeField(default=timezone.now)

    def get_upload_path(instance, file_name):
        return 'exports/{}'.format(instance.file_name)

    file = models.FileField(upload_to=get_upload_path)


    def to_model_view(self):
        return {
            k_name: self.name,
            k_file_url: MediaUtil.to_media_url(self.file.url),
            k_file_name: self.file_name,
            k_description: self.description,
            k_created_at: FormattingUtil.to_timestamp(self.created),
        }

