import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models.geo import Address
from apps.core.models.settings import Settings


class User(AbstractUser):
    # Any additional fields can go here
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    first_name = models.CharField(max_length=64, null=True)

    last_name = models.CharField(max_length=64, null=True)

    email = models.CharField(max_length=64, null=False)

    fcm_token = models.CharField(max_length=256, null=True)

    password = models.CharField(max_length=256, null=False)

    salt = models.CharField(max_length=256, null=True)

    description = models.CharField(max_length=256, null=True, blank=True)

    profile_picture = models.ImageField(upload_to='users/{}/profile_picture'.format(id), null=True)

    initials = models.CharField(max_length=16, null=True)

    phone_number = models.CharField(max_length=64, null=True)

    tax_number = models.CharField(max_length=64, null=True)  #IBAN

    company_name = models.CharField(max_length=64, null=True)  #SSN

    address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='address', default='')

    billing_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='billing_address',
                                        default='')

    date_of_birth = models.DateField(null=True)

    settings = models.ForeignKey(Settings, null=True, on_delete=models.CASCADE, related_name='settings')

    accepted = models.BooleanField(default=True, null=False)

    hours = models.FloatField(default=0, null=True)

    archived = models.BooleanField(default=False, )
    session_duration = models.IntegerField(null=True)

    place_of_birth = models.CharField(max_length=30, null=True)
