from rest_framework import serializers
from .utils import WorkerUtil

from .models import DashboardFlow
from .models.profiles.worker_profile import WorkerProfile


class WorkerProfileSerializer(serializers.ModelSerializer):

    """
    Serializer for the WorkerProfile model.

    This serializer includes all fields from the WorkerProfile model 
    and provides additional computed fields:
    
    - 'completion_percentage': The percentage of profile completion based on mandatory fields.
    - 'missing_fields': A list of mandatory fields that are missing or incomplete.

    These fields are calculated using the WorkerUtil.calculate_profile_completion function.
    """

    completion_percentage = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta:
        model = WorkerProfile
        fields = '__all__'
        extra_fields = ["completion_percentage", "missing_fields"]

    def get_completion_percentage(self, obj):

        """
        Get the completion percentage data from worker's profile.

        Args:
        self (WorkerProfileSerializer): instance of WorkerProfileSerializer.
        obj (WorkerProfile): instance of WorkerProfile.

        Returns:
        int: percentage of worker's profile completion
        """

        completion_data = WorkerUtil.calculate_profile_completion(obj.user)  # Get user from profile
        return completion_data["completion_percentage"]

    def get_missing_fields(self, obj):

        """
        Get the missing fields from the worker's profile.

        Args:
        self (WorkerProfileSerializer): instance of WorkerProfileSerializer.
        obj (WorkerProfile): instance of WorkerProfile.

        Returns:
        Dictionnary of missing fields.
        
        """
        completion_data = WorkerUtil.calculate_profile_completion(obj.user)
        return completion_data["missing_fields"]



class DashboardFlowSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardFlow
        fields = '__all__'
