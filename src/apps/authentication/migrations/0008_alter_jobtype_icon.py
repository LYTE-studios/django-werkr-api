# Generated by Django 4.2.17 on 2025-01-30 11:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0007_situationtype_worktype_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobtype',
            name='icon',
            field=models.CharField(max_length=1024, null=True),
        ),
    ]
