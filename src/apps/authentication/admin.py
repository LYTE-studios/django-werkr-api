

from django.contrib import admin
from .models import Location, JobType, SituationType, WorkType

admin.site.register(Location)
admin.site.register(JobType)
admin.site.register(SituationType)
admin.site.register(WorkType)