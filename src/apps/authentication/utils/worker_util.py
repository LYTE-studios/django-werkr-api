from django.contrib.auth import get_user_model

User = get_user_model()

from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .profile_util import ProfileUtil


class WorkerUtil:

    @staticmethod
    def to_worker_view(worker: User):
        # Required data
        data = {k_id: worker.id, k_first_name: worker.first_name,
                k_last_name: worker.last_name,
                k_email: worker.email, k_created_at: FormattingUtil.to_timestamp(worker.date_joined),
                k_tax_number: worker.tax_number,
                k_company: worker.company_name,
                k_hours: worker.hours,
                }

        try:
            data[k_address] = worker.address.to_model_view()
        except Exception:
            pass
        try:
            data[k_date_of_birth] = FormattingUtil.to_timestamp(worker.date_of_birth)
        except Exception:
            pass
        try:
            data[k_profile_picture] = ProfileUtil.get_user_profile_picture_url(worker)
        except Exception:
            pass

        return data
