# Generated by Django 4.2.19 on 2025-02-28 10:12

from django.db import migrations, models


class Migration(migrations.Migration):

    """
    Migration that alters an existing field in a model to the dabatase.
    The altered fields are as follow:

    - Altering 'from_lat', 'from_lon', 'to_lat', 'to_lon' fields in 'storeddirections' model by:
    Changing the type of the field to 'FloatField'.
    Necessary to allow the fields to store floating point numbers.

    """

    dependencies = [
        ('jobs', '0002_alter_job_application_start_time_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storeddirections',
            name='from_lat',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='storeddirections',
            name='from_lon',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='storeddirections',
            name='to_lat',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='storeddirections',
            name='to_lon',
            field=models.FloatField(),
        ),
    ]
