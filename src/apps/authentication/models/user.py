import uuid
from apps.core.models.settings import Settings
from apps.core.utils.wire_names import *
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=64, null=True)
    last_name = models.CharField(max_length=64, null=True)
    email = models.CharField(max_length=64, null=False)
    fcm_token = models.CharField(max_length=256, null=True)
    password = models.CharField(max_length=256, null=True)
    salt = models.CharField(max_length=256, null=True)
    description = models.CharField(max_length=256, null=True, blank=True)
    phone_number = models.CharField(max_length=64, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='users/{}/profile_picture'.format(id), null=True)
    settings = models.ForeignKey(Settings, null=True, on_delete=models.CASCADE, related_name='settings')
    archived = models.BooleanField(default=False)

    def is_accepted(self):
        if self.archived:
            return False

        if self.is_worker():
            return self.worker_profile.accepted
        
        return True

    def is_worker(self):
        if hasattr(self, 'worker_profile'):
            return True
        return False

    def is_customer(self):
        if hasattr(self, 'customer_profile'):
            return True
        return False

    def is_admin(self):
        if hasattr(self, 'admin_profile'):
            return True
        return False
