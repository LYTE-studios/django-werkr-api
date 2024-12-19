from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from .profile_util import ProfileUtil


class CustomerUtil:

    @staticmethod
    def to_customer_view(customer, has_active_job: bool = False):
        # Required data
        data = {k_id: customer.id, k_initials: customer.initials, k_first_name: customer.first_name,
                k_last_name: customer.last_name,
                k_email: customer.email, k_created_at: FormattingUtil.to_timestamp(customer.date_joined),
                k_phone_number: customer.phone_number,
                k_address: customer.address.to_model_view(),
                k_billing_address: customer.billing_address.to_model_view(),
                k_tax_number: customer.tax_number,
                k_company: customer.company_name,
                k_hours: customer.hours,
                k_has_active_job: has_active_job,
                }

        try:
            data[k_profile_picture] = ProfileUtil.get_user_profile_picture_url(
                customer, )
        except Exception:
            pass

        return data
