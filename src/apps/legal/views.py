from django.shortcuts import get_object_or_404
from apps.jobs.models.application import JobApplication
from rest_framework.views import APIView

from .utils.contract_util import ContractUtil
from apps.authentication.views import JWTBaseAuthView
from django.http import HttpRequest, HttpResponse
from rest_framework.response import Response
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
import uuid


class DownloadContractView(JWTBaseAuthView):
    """
    A view for workers to download their contract if their application is approved.
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        # Initialize the formatter with the request kwargs
        formatter = FormattingUtil(kwargs)
        # Retrieve the application ID from the formatted kwargs
        application_id = formatter.get_value(value_key=k_id)

        # Fetch the JobApplication object or return a 404 if not found
        job_application = get_object_or_404(JobApplication, id=application_id)

        try:
            # Retrieve the worker profile associated with the job application
            worker_profile = job_application.worker.worker_profile
        except Exception as e:
            # Return a 404 response if the worker profile is not found
            return HttpResponse(str(e), status=404)

        try:
            # Retrieve the customer profile associated with the job application
            customer_profile = job_application.job.customer.customer_profile
        except Exception as e:
            # Return a 404 response if the customer profile is not found
            return HttpResponse(str(e), status=404)

        # Check if the job application is approved
        if not job_application.application_state == "approved":
            # Return a 400 response if the application is not approved
            return HttpResponse("Worker not approved", status=400)

        # Check if a contract already exists for the job application
        if job_application.contract:
            # Use the existing contract path
            contract_path = job_application.contract.path
        else:
            # Generate a new contract and save the path to the job application
            contract_path = ContractUtil.generate_contract(customer_profile, worker_profile)
            job_application.contract = contract_path
            job_application.save()

        # Open the contract file and create an HTTP response with the file content
        with open(contract_path, 'rb') as contract_file:
            response = HttpResponse(contract_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{worker_profile.user.id}_contract.pdf"'
            return response