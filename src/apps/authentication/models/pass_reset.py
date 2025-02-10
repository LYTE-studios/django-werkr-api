import uuid

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class PassResetCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="pass_reset_user"
    )
    code = models.CharField(max_length=6, null=False)
    generated_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False, null=False)
    reset_password_token = models.CharField(max_length=100, blank=True, null=True)
    token_expiry_time = models.DateTimeField(blank=True, null=True)
