from django.contrib.auth import get_user_model

from src.apps.authentication.models.profiles.worker_profile import WorkerProfile

User = get_user_model()

from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .profile_util import ProfileUtil


class WorkerUtil:

    @staticmethod
    def to_worker_view(worker: User):
        # Required data
        data = {
            k_id: worker.id, k_first_name: worker.first_name,
            k_last_name: worker.last_name,
            k_email: worker.email, k_created_at: FormattingUtil.to_timestamp(worker.date_joined),
            k_iban: worker.worker_profile.iban,
            k_ssn: worker.worker_profile.ssn,
            k_phone_number: worker.phone_number,
            k_worker_type: worker.worker_profile.worker_type,
        }

        try:
            data[k_address] = worker.worker_profile.worker_address.to_model_view()
        except Exception:
            pass
        try:
            data[k_date_of_birth] = FormattingUtil.to_timestamp(worker.worker_profile.date_of_birth)
        except Exception:
            pass
        try:
            data[k_profile_picture] = ProfileUtil.get_user_profile_picture_url(worker)
        except Exception:
            pass

        return data
    
    @staticmethod
    def calculate_worker_completion(worker):
        """
        Calculates the worker's profile completion percentage and identifies missing fields.

        Args:
        worker (User): A User instance in WorkerProfile.

        Returns:
        A dictionnary of the completion percentage and the missing fields.

        """

        # Get worker's data using the existing function
        worker_data = WorkerProfile.to_worker_view(worker)

        # Define mandatory fields for profile completion
        mandatory_fields = ["first_name", "last_name", "email", "iban", "ssn", "phone_number"]

        # Find missing fields
        missing_fields = [field for field in mandatory_fields if not worker_data.get(field)]

        # Calculate completion percentage
        total_fields = len(mandatory_fields)
        completed_fields = total_fields - len(missing_fields)
        completion_percentage = int((completed_fields / total_fields) * 100)

        return {
            "completion_percentage": completion_percentage,
            "missing_fields": missing_fields
        }


    

