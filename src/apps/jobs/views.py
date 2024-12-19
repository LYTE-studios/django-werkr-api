from http import HTTPStatus

from django.http import HttpRequest, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest, Http404
from rest_framework.response import Response
from apps.authentication.views import JWTBaseAuthView
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.core.model_exceptions import DeserializationException
from apps.jobs.managers.job_manager import JobManager
from apps.core.assumptions import *
import datetime
from apps.jobs.services.contract_service import JobApplicationService
from apps.jobs.services.job_service import JobService
from django.core.paginator import Paginator


class JobView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting job details
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        job_id = kwargs['id']
        job_details = JobService.get_job_details(job_id)
        return Response(data=job_details)

    def delete(self, request: HttpRequest, *args, **kwargs):
        job_id = kwargs['id']
        try:
            JobService.delete_job(job_id)
        except Http404:
            return HttpResponseNotFound()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        job_id = kwargs['id']
        try:
            JobService.update_job(job_id, request.data)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response()


class CreateJobView(JWTBaseAuthView):
    """
    [CMS]

    POST

    View to create a job.

    Returns Job id when valid.
    """

    app_types = [
        CMS_GROUP_NAME
    ]

    def post(self, request: HttpRequest):
        try:
            job_id = JobService.create_job(request.data)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response({k_job_id: job_id})


class UpcomingJobsView(JWTBaseAuthView):
    """
    [Workers]

    GET

    A view for workers to get their upcoming jobs
    """

    groups = [
        WASHERS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest):
        jobs = JobService.get_upcoming_jobs(self.user, is_worker=True)
        return Response({k_jobs: jobs})


class AllUpcomingJobsView(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view for admin users to get upcoming jobs
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        formatter = FormattingUtil(kwargs)
        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)
        jobs = JobService.get_upcoming_jobs(self.user, is_worker=False, start=start, end=end)
        return Response({k_jobs: jobs})


class HistoryJobsView(JWTBaseAuthView):
    """
    [Workers]

    GET

    A view for workers to get their upcoming jobs
    """

    groups = [
        WASHERS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        end = datetime.datetime.now()
        start = datetime.datetime.fromtimestamp(0)
        try:
            start = FormattingUtil.to_date_time(kwargs['start'])
            end = FormattingUtil.to_date_time(kwargs['end'])
        except KeyError:
            pass
        jobs = JobService.get_history_jobs(self.user, start, end)
        return Response({k_jobs: jobs})


class GetJobsBasedOnUserView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME,
        CUSTOMERS_GROUP_NAME,
    ]

    def post(self, request, *args, **kwargs):
        formatter = FormattingUtil(data=request.data)
        try:
            worker_id = formatter.get_value(k_worker_id)
            customer_id = formatter.get_value(k_customer_id)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        jobs = JobService.get_jobs_based_on_user(worker_id, customer_id)
        return Response({k_jobs: jobs})


class TimeRegistrationView(JWTBaseAuthView):
    app_types = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME
    ]

    def get(self, request: HttpRequest):
        formatter = FormattingUtil(data=request.data)
        try:
            job_id = formatter.get_value(k_job_id, required=True)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        times = JobService.get_time_registrations(job_id)
        return Response({k_times: times})

    def post(self, request: HttpRequest, *args, **kwargs):
        try:
            job_id = JobService.register_time(request.data, self.user)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        return Response({k_job_id: job_id}, status=HTTPStatus.OK)


class SignTimeRegistrationView(JWTBaseAuthView):
    app_types = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        try:
            time_registration_id = JobService.sign_time_registration(request.data)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response({k_id: time_registration_id}, status=HTTPStatus.OK)


class ActiveJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        jobs = JobService.get_active_jobs()
        return Response({k_jobs: jobs})


class DoneJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        formatter = FormattingUtil(kwargs)
        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)
        jobs = JobService.get_done_jobs(start, end)
        return Response({k_jobs: jobs})


class DraftJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        jobs = JobService.get_draft_jobs()
        return Response({k_jobs: jobs})


class ApplicationView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting application details
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        try:
            application_data = JobApplicationService.get_application_details(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response(data=application_data)

    def delete(self, request: HttpRequest, *args, **kwargs):
        try:
            JobApplicationService.delete_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()


class ApproveApplicationView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for approving applications
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        try:
            JobApplicationService.approve_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()


class DenyApplicationView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for Denying applications
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        try:
            JobApplicationService.deny_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()


class DirectionsView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        from_lat = int(kwargs.get('from_lat', 0)) / 1000000
        from_lon = int(kwargs.get('from_lon', 0)) / 1000000
        to_lat = int(kwargs.get('to_lat', 0)) / 1000000
        to_lon = int(kwargs.get('to_lon', 0)) / 1000000

        response = JobApplicationService.fetch_directions(from_lat, from_lon, to_lat, to_lon)

        if response.ok:
            return HttpResponse(response.content)

        return HttpResponseBadRequest(response.content)


class MyApplicationsView(JWTBaseAuthView):
    """
    [Workers]

    GET | POST

    A view for workers to view their applications and add new ones
    """

    def get(self, request: HttpRequest):
        application_model_list = JobApplicationService.get_my_applications(self.user)
        return Response({k_applications: application_model_list})

    def post(self, request: HttpRequest):
        try:
            application_id = JobApplicationService.create_application(request.data, self.user)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except ValueError as e:
            return Response({k_message: str(e)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return Response({k_id: application_id})


class ApplicationsListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get applications details
    """

    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        applications = JobApplicationService.get_applications_list(kwargs.get('job_id'))
        paginator = Paginator(applications, per_page=25)
        data = [application.to_model_view() for application in applications]

        return Response({k_applications: data, k_items_per_page: paginator.per_page, k_total: len(applications)})
