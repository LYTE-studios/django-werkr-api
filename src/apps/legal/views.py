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

        # Check if the job application is approved
        if not job_application.application_state == "approved":
            # Return a 400 response if the application is not approved
            return HttpResponse("Worker not approved", status=400)

        # Generate or get the contract path
        contract_path = ContractUtil.generate_contract(job_application)

        # Open and read the contract file
        with open(contract_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename=contract_{job_application.id}.pdf'
            return response