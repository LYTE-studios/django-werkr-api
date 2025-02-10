from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="admin_profile"
    )
    session_duration = models.IntegerField(null=True)
