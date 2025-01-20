import uuid
from django.db import models
from django.contrib.auth import get_user_model
from .job_type import JobType
from .location import Location

User = get_user_model()


class DashboardFlow(models.Model):

    class ExperienceType(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        SKILLED = 'skilled', 'Skilled'
        EXPERT = 'expert', 'Expert'

    class SituationType(models.TextChoices):
        FLEXI = 'flexi', 'Flexi'
        STUDENT = 'student', 'Student'
        PARTTIME = 'part_time', 'Part Time'
        NEITHER = 'neither', 'Neither'

    class WorkType(models.TextChoices):
        WEEKDAYMORNINGS = 'weekday_mornings', 'Weekday Mornings'
        WEEKDAYEVENINGS = 'weekday_evenings', 'Weekday Evenings'
        WEEKENDS = 'weekends', 'Weekends'
        ALLWEEK = 'all_week', 'All Week'
        HOLIDAYS = 'holidays', 'Holidays'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_flow_user')
    job_type = models.ManyToManyField(JobType, related_name='dashboard_flow_job_type')
    car_washing_experience_type = models.CharField(max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER)
    waiter_experience_type = models.CharField(max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER)
    cleaning_experience_type = models.CharField(max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER)
    chauffeur_experience_type = models.CharField(max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER)
    gardening_experience_type = models.CharField(max_length=20, choices=ExperienceType.choices, default=ExperienceType.BEGINNER)
    situation_type = models.CharField(max_length=20, choices=SituationType.choices, default=SituationType.FLEXI)
    work_type = models.CharField(max_length=20, choices=WorkType.choices, default=WorkType.WEEKDAYMORNINGS)
    locations = models.ManyToManyField(Location, related_name='dashboard_flow_location')

