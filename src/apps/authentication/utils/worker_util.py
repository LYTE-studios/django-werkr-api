from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .profile_util import ProfileUtil


class WorkerUtil:

    @staticmethod
    def to_worker_view(worker):
        # Required data
        data = {
            k_id: worker.id,
            k_first_name: worker.first_name,
            k_last_name: worker.last_name,
            k_email: worker.email,
            k_created_at: FormattingUtil.to_timestamp(worker.date_joined),
            k_phone_number: worker.phone_number,
        }

        if hasattr(worker, 'worker_profile'):
            worker_profile = worker.worker_profile
            data.update({
                k_iban: worker_profile.iban,
                k_ssn: worker_profile.ssn,
                k_worker_type: worker_profile.worker_type,
            })

            try:
                data[k_address] = worker_profile.worker_address.to_model_view()
            except Exception:
                pass
            try:
                data[k_date_of_birth] = FormattingUtil.to_timestamp(worker_profile.date_of_birth)
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

        worker_data = {
            "iban": worker.worker_profile.iban,
            "ssn": worker.worker_profile.ssn,
            "worker_address": worker.worker_profile.worker_address,
            "date_of_birth": worker.worker_profile.date_of_birth,
            "place_of_birth": worker.worker_profile.place_of_birth,
        }

        # Find missing fields
        missing_fields = [field for field in worker_data.keys() if not worker_data[field]]

        if not missing_fields:
            return 100, []

        # Calculate completion percentage
        total_fields = len(worker_data)
        completed_fields = total_fields - len(missing_fields)
        completion_percentage = int((completed_fields / total_fields) * 100)

        return completion_percentage, missing_fields


    

