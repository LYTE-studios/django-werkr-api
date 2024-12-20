import uuid

from apps.core.models.settings import Settings
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=64, null=True)
    last_name = models.CharField(max_length=64, null=True)
    email = models.CharField(max_length=64, null=False)
    fcm_token = models.CharField(max_length=256, null=True)
    password = models.CharField(max_length=256, null=False)
    salt = models.CharField(max_length=256, null=True)
    description = models.CharField(max_length=256, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='users/{}/profile_picture'.format(id), null=True)
    settings = models.ForeignKey(Settings, null=True, on_delete=models.CASCADE, related_name='settings')
    archived = models.BooleanField(default=False)

    accepted = models.BooleanField(default=True, null=False)

    hours = models.FloatField(default=0, null=True)

    archived = models.BooleanField(default=False, )
    session_duration = models.IntegerField(null=True)

    place_of_birth = models.CharField(max_length=30, null=True)

    def to_worker_view(self):
        # Required data
        data = {k_id: self.id, k_first_name: self.first_name, k_last_name: self.last_name, k_email: self.email, }

        # Optional data
        try:
            data[k_profile_picture] = MediaUtil.to_media_url(self.profile_picture.url)
        except:
            pass
        try:
            data[k_company] = self.company_name
            data[k_phone_number] = self.phone_number
            data[k_tax_number] = self.tax_number
            data[k_date_of_birth] = FormattingUtil.to_timestamp(self.date_of_birth)
        except Exception:
            pass

        return data
