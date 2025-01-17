from django.db import models
from django.contrib.auth.models import Group


class CustomGroup(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='extension'
    )
    group_secret = models.CharField(max_length=180, null=True)

    class Meta:
        app_label = 'authentication'
