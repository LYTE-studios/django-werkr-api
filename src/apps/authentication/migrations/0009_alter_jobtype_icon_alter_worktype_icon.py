# Generated by Django 4.2.17 on 2025-01-30 11:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_alter_jobtype_icon'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobtype',
            name='icon',
            field=models.CharField(max_length=4048, null=True),
        ),
        migrations.AlterField(
            model_name='worktype',
            name='icon',
            field=models.CharField(max_length=4048, null=True),
        ),
    ]
