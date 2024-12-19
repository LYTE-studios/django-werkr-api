import datetime
from django.contrib.auth import get_user_model

User = get_user_model()
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.authentication.utils.customer_util import CustomerUtil
from apps.jobs.models.time_registration import TimeRegistration


class JobUtil:

    @staticmethod
    def to_model_view(job):
        customer = User.objects.get(id=job.customer_id)
        address1 = job.address

        registrations = []

        time_registrations = TimeRegistration.objects.filter(job_id=job.id)

        for registration in time_registrations:
            registrations.append(registration.to_model_view())

        return {
            k_id: job.id,
            k_title: job.title,
            k_description: job.description,
            k_time_registrations: registrations,
            k_address: {
                k_street_name: address1.street_name,
                k_house_number: address1.house_number,
                k_box_number: address1.box_number,
                k_city: address1.city,
                k_zip_code: address1.zip_code,
                k_country: address1.country,
                k_latitude: address1.latitude,
                k_longitude: address1.longitude,
            },
            k_start_time: FormattingUtil.to_timestamp(job.start_time),
            k_end_time: FormattingUtil.to_timestamp(job.end_time),
            k_application_start_time: FormattingUtil.to_timestamp(job.application_start_time),
            k_application_end_time: FormattingUtil.to_timestamp(job.application_end_time),
            k_max_workers: job.max_workers,
            k_is_draft: job.is_draft,
            k_selected_workers: job.selected_workers,
            k_state: job.job_state,
            k_customer: CustomerUtil.to_customer_view(customer),
        }
