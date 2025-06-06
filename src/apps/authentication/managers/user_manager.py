import datetime

from apps.authentication.models.profiles.customer_profile import CustomerProfile
from apps.authentication.models.profiles.worker_profile import WorkerProfile
from apps.core.models.geo import Address
from apps.core.models.settings import Settings
from django.contrib.auth import get_user_model

User = get_user_model()


class UserManager:
    """
    Manager for performing user tasks
    """

    @staticmethod
    def create_user(user: User):
        # Get the default settings
        settings = Settings.get_default()

        # Set the settings
        user.settings = settings

        # Save the user
        user.save()

        return User.objects.get(email=user.email)

    @staticmethod
    def create_worker_profile(user: User, iban: str = None, ssn: str = None, worker_address: Address = None,
                              date_of_birth: datetime.date = None, place_of_birth: str = None):
        worker_profile = WorkerProfile(
            user=user,
            iban=iban,
            ssn=ssn,
            worker_address=worker_address,
            date_of_birth=date_of_birth,
            place_of_birth=place_of_birth,
            accepted=False,
        )
        worker_profile.save()

    @staticmethod
    def create_customer_profile(user: User, tax_number: str = None, company_name: str = None,
                                customer_address: Address = None, customer_billing_address: Address = None):
        # Get or update existing profile
        customer_profile, created = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                'tax_number': tax_number,
                'company_name': company_name,
                'customer_address': customer_address,
                'customer_billing_address': customer_billing_address
            }
        )
        
        if not created:
            # Update existing profile
            customer_profile.tax_number = tax_number or customer_profile.tax_number
            customer_profile.company_name = company_name or customer_profile.company_name
            customer_profile.customer_address = customer_address or customer_profile.customer_address
            customer_profile.customer_billing_address = customer_billing_address or customer_profile.customer_billing_address
            customer_profile.save()
