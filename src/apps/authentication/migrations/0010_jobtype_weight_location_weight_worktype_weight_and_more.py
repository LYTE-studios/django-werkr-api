# Generated by Django 4.2.17 on 2025-01-30 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0009_alter_jobtype_icon_alter_worktype_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobtype',
            name='weight',
            field=models.IntegerField(default=0, max_length=16),
        ),
        migrations.AddField(
            model_name='location',
            name='weight',
            field=models.IntegerField(default=0, max_length=16),
        ),
        migrations.AddField(
            model_name='worktype',
            name='weight',
            field=models.IntegerField(default=0, max_length=16),
        ),
        migrations.AlterField(
            model_name='jobtype',
            name='icon',
            field=models.CharField(max_length=32768, null=True),
        ),
        migrations.AlterField(
            model_name='worktype',
            name='icon',
            field=models.CharField(max_length=32768, null=True),
        ),
    ]
