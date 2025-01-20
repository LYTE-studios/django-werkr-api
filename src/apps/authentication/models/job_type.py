from django.db import models


class JobType(models.Model):
    CARWASHING = 'car_washing'
    WAITER = 'waiter'
    CLEANING = 'cleaning'
    CHAUFFEUR = 'chauffeur'
    GARDENING = 'gardening'
    OTHER = 'other'

    JOB_TYPE_CHOICES = [
        (CARWASHING, 'Car Washing'),
        (WAITER, 'Waiter'),
        (CLEANING, 'Cleaning'),
        (CHAUFFEUR, 'Chauffeur'),
        (GARDENING, 'Gardening'),
        (OTHER, 'Other'),
    ]

    name = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, unique=True)