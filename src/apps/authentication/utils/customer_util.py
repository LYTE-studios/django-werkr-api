from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *

from .profile_util import ProfileUtil


class CustomerUtil:

    @staticmethod
    def to_customer_view(customer, has_active_job: bool = False):
        # Check if the related CustomerProfile exists
        if not hasattr(customer, "customer_profile"):
            return {"error": "Customer profile does not exist for this user."}

        customer_profile = customer.customer_profile

        # Required data
        data = {
            k_id: customer.id,
            k_first_name: customer.first_name,
            k_last_name: customer.last_name,
            k_email: customer.email,
            k_created_at: FormattingUtil.to_timestamp(customer.date_joined),
            k_address: customer_profile.customer_address.to_model_view(),
            k_billing_address: customer_profile.customer_billing_address.to_model_view(),
            k_tax_number: customer_profile.tax_number,
            k_company: customer_profile.company_name,
            k_has_active_job: has_active_job,
            k_phone_number: customer.phone_number,
            k_special_committee: customer_profile.special_committee,
        }

        try:
            data[k_profile_picture] = ProfileUtil.get_user_profile_picture_url(customer)
        except Exception:
            pass

        return data
