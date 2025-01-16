# apps/legal/management/commands/create_contracts.py

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.jobs.models import JobApplication, JobApplicationState  # Adjust the import path to your actual JobApplication model
from apps.legal.utils import ContractUtil  # Adjust the import path to your actual ContractUtil

class Command(BaseCommand):
    help = 'Create contracts for approved job applications without contracts'

    def handle(self, *args, **kwargs):
        job_applications_without_contracts = JobApplication.objects.filter(
            # contract__isnull=True,
            application_state=JobApplicationState.approved
        )

        for application in job_applications_without_contracts:
            try:
                ContractUtil.generate_contract(application)

                self.stdout.write(self.style.SUCCESS(f"Contract created for application ID: {application.id}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to create contract for application ID: {application.id}, Error: {str(e)}"))

