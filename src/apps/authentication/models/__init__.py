from django.contrib.auth.models import Group
from django.db import models

Group.add_to_class('secret', models.CharField(max_length=180, null=True, ), )

from .user import User
