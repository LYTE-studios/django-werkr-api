from django.contrib.auth.models import Group
from django.db import models

Group.add_to_class('secret', models.CharField(max_length=180, null=True, ), )

from .user import User
from .profiles.admin_profile import AdminProfile
from .profiles.customer_profile import CustomerProfile
from .profiles.worker_profile import WorkerProfile
from .pass_reset import PassResetCode
from .favorite_address import FavoriteAddress
