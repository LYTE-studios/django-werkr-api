from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # Any additional fields can go here
    email = models.EmailField(unique=True)
    date_of_birth = models.DateField(null=True, blank=True)