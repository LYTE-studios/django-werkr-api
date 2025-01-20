from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models.geo import Address

User = get_user_model()


class WorkerProfile(models.Model):
    class WorkerType(models.TextChoices):
        FREELANCER = 'freelancer', 'Freelancer'
        STUDENT = 'student', 'Student'
        FLEXI = 'flexi', 'Flexi'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker_profile')
    iban = models.CharField(max_length=64, null=True)
    ssn = models.CharField(max_length=64, null=True)
    worker_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='worker_address')
    date_of_birth = models.DateField(null=True)
    place_of_birth = models.CharField(max_length=30, null=True)
    accepted = models.BooleanField(default=True, null=False)
    hours = models.FloatField(default=0, null=True)
    worker_type = models.CharField(max_length=10, choices=WorkerType.choices, default=WorkerType.STUDENT)
    # Once a Worker registers, their account should get a “flag” that indicates that they have not yet done a onboarding flow
    has_passed_onboarding = models.BooleanField(default=False)
