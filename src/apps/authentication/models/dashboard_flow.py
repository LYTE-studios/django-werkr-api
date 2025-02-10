import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.utils.wire_names import *

User = get_user_model()


class ExperienceType(models.TextChoices):
    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    SKILLED = "skilled", "Skilled"
    EXPERT = "expert", "Expert"


class Location(models.Model):
    name = models.CharField(max_length=64, null=True)

    weight = models.IntegerField(max_length=16, default=0)

    def __str__(self):
        return self.name + " at " + str(self.weight)

    def to_model_view(self):
        return {
            k_id: self.id,
            k_name: self.name,
        }


class JobType(models.Model):

    icon = models.CharField(max_length=32768, null=True)

    name = models.CharField(max_length=32, unique=True, null=False)

    weight = models.IntegerField(max_length=16, default=0)

    def __str__(self):
        return self.name + " at " + str(self.weight)

    def to_model_view(self):
        return {
            k_id: self.id,
            k_icon: self.icon,
            k_name: self.name,
        }


class UserJobType(models.Model):

    name = models.ForeignKey(JobType, on_delete=models.CASCADE)

    experience_type = models.CharField(
        max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER
    )


class SituationType(models.Model):
    name = models.CharField(max_length=32, unique=True, null=False)

    weight = models.IntegerField(max_length=16, default=0)

    def __str__(self):
        return self.name + " at " + str(self.weight)

    def to_model_view(self):
        return {
            k_id: self.id,
            k_name: self.name,
        }


class WorkType(models.Model):
    icon = models.CharField(max_length=32768, null=True)

    name = models.CharField(max_length=32, unique=True, null=False)

    weight = models.IntegerField(max_length=16, default=0)

    def __str__(self):
        return self.name + " at " + str(self.weight)

    def to_model_view(self):
        return {
            k_id: self.id,
            k_name: self.name,
            k_icon: self.icon,
        }


class DashboardFlow(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dashboard_flow_user"
    )

    situation_types = models.ManyToManyField(
        SituationType, related_name="dashboard_flow_situation_type"
    )

    job_types = models.ManyToManyField(
        UserJobType, related_name="dashboard_flow_job_type"
    )

    work_types = models.ManyToManyField(
        WorkType, related_name="dashboard_flow_work_type"
    )

    locations = models.ManyToManyField(Location, related_name="dashboard_flow_location")
