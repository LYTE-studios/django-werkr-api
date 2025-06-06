# Generated by Django 5.1.4 on 2025-01-10 09:11

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    """
    Migration that alters an existing field in a model to the dabatase.
    The altered fields are as follow:

    - Altering 'application_start_time' field in 'job' model:
      - Allowing the field to be blank.
      - Setting the default value of the field to the current timestamp.
      - Allowing the field to store 'null' in the database.

    - Altering 'start_time' field in 'job' model:
      - Setting the default value of the field to the current timestamp.
    

    This migration will alter the fields of the corresponding models in the database.
    """

    dependencies = [
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='application_start_time',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='start_time',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
