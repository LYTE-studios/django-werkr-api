from rest_framework import serializers

from .models import DashboardFlow
from .models.profiles.worker_profile import WorkerProfile


class WorkerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerProfile
        fields = "__all__"


class DashboardFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardFlow
        fields = "__all__"
