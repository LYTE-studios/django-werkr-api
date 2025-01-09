from django.shortcuts import get_object_or_404
from apps.jobs.models.application import JobApplication
from rest_framework.views import APIView

from .utils.contract_util import generate_contract
from apps.authentication.views import JWTBaseAuthView
from django.http import HttpRequest, HttpResponse
from rest_framework.response import Response
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
import uuid


class DownloadContractView(JWTBaseAuthView):
    """
    [Workers]

    GET | POST

    A view for workers to view their applications and add new ones.
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        formatter = FormattingUtil(kwargs)
        # application_id = uuid.UUID(formatter.get_value(value_key=k_id)).hex
        application_id = formatter.get_value(value_key=k_id)

        job_application = get_object_or_404(JobApplication, id=application_id)
        worker_profile = job_application.worker
        customer_profile = job_application.job.customer

        if not job_application.application_state == "approved":
            return HttpResponse("Worker not approved", status=400)

        contract_path = generate_contract(customer_profile, worker_profile)
        job_application.contract = contract_path
        job_application.save()
        with open(contract_path, 'rb') as contract_file:
            response = HttpResponse(contract_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{worker_profile.user.id}_contract.pdf"'
            return response
