from django.contrib.auth.models import Group
from django.db import models
from django.conf import settings

from .user import User
from .custom_group import CustomGroup
from .profiles.admin_profile import AdminProfile
from .profiles.customer_profile import CustomerProfile
from .profiles.worker_profile import WorkerProfile
from .pass_reset import PassResetCode
from .favorite_address import FavoriteAddress
from .dashboard_flow import DashboardFlow, JobType, Location, WorkType, SituationType, UserJobType

# Create the groups from the Django assumptions

from apps.core.assumptions import *

group, updated = Group.objects.update_or_create(name=CUSTOMERS_GROUP_NAME)

if updated:
    CustomGroup.objects.create(group=group, group_secret=settings.CUSTOMER_GROUP_SECRET)

group, updated = Group.objects.update_or_create(name=WORKERS_GROUP_NAME)

if updated:
    CustomGroup.objects.create(group=group, group_secret=settings.WORKER_GROUP_SECRET)

group, updated = Group.objects.update_or_create(name=CMS_GROUP_NAME)

if updated:
    CustomGroup.objects.create(group=group, group_secret=settings.CMS_GROUP_SECRET)