from http import HTTPStatus
import requests

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone

from apps.authentication.views import JWTBaseAuthView
from apps.core.assumptions import *
from apps.core.model_exceptions import DeserializationException
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.services.contract_service import JobApplicationService
from apps.jobs.services.job_service import JobService
from apps.jobs.models.dimona import Dimona
from apps.jobs.models.job import Job
from apps.jobs.models.time_registration import TimeRegistration
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, Http404
from rest_framework.response import Response
from apps.authentication.utils.worker_util import WorkerUtil

from apps.jobs.models.application import JobApplication
from apps.jobs.models.job_application_state import JobApplicationState
from apps.jobs.services.statistics_service import StatisticsService
from apps.core.models.export_file import ExportFile
from apps.jobs.services.export_service import ExportManager


class JobView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting job details.
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handle GET request to retrieve job details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing job details.
        """
        job_id = kwargs['id']
        job_details = JobService.get_job_details(job_id)
        return Response(data=job_details)

    def delete(self, request: HttpRequest, *args, **kwargs):
        """
        Handle DELETE request to delete a job.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object indicating the result of the delete operation.
        """
        job_id = kwargs['id']
        try:
            JobService.delete_job(job_id)
        except Http404:
            return HttpResponseNotFound()

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        """
        Handle PUT request to update a job.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object indicating the result of the update operation.
        """
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
        """
        Handle POST request to create a job.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the job id if creation is successful.
        """
        try:
            job_id = JobService.create_job(request.data)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        
        return Response({k_job_id: job_id})


class UpcomingJobsView(JWTBaseAuthView):
    """
    [Workers]

    GET

    A view for workers to get their upcoming jobs.
    """

    groups = [
        WORKERS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest):
        """
        Handle GET request to retrieve upcoming jobs for workers.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the list of upcoming jobs.
        """
        jobs = JobService.get_upcoming_jobs(self.user, is_worker=True)
        return Response({k_jobs: jobs})


class AllUpcomingJobsView(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view for admin users to get upcoming jobs.
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handle GET request to retrieve upcoming jobs for admin users.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of upcoming jobs.
        """
        formatter = FormattingUtil(kwargs)
        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)
        jobs = JobService.get_upcoming_jobs(self.user, is_worker=False, start=start, end=end)
        return Response({k_jobs: jobs})


class HistoryJobsView(JWTBaseAuthView):
    """
    [Workers]

    GET

    A view for workers to get their upcoming jobs.
    """

    groups = [
        WORKERS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handle GET request to retrieve history jobs for workers.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of history jobs.
        """
        end = timezone.now()
        start = timezone.datetime.fromtimestamp(0)
        try:
            start = FormattingUtil.to_date_time(kwargs['start'])
            end = FormattingUtil.to_date_time(kwargs['end'])
        except KeyError:
            pass
        jobs = JobService.get_history_jobs(self.user, start, end)
        return Response({k_jobs: jobs})


class GetJobsBasedOnUserView(JWTBaseAuthView):
    """
    [CMS, Workers, Customers]

    POST

    A view to get jobs based on user.
    """

    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
        CUSTOMERS_GROUP_NAME,
    ]

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to retrieve jobs based on user.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of jobs based on user.
        """
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
    """
    [CMS, Workers]

    GET | POST

    A view for time registration.
    """

    app_types = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME
    ]

    def get(self, request: HttpRequest, job_id: str) -> Response:
        """
        Handle GET request to retrieve time registrations.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the list of time registrations.
        """
        get_object_or_404(Job, id=job_id)

        try:
            registration = TimeRegistration.objects.get(job_id=job_id, worker_id=request.user.id)

            return Response({k_time_registration: registration.to_model_view()})

        except TimeRegistration.DoesNotExist:
            return Response()

    def post(self, request: HttpRequest, *args, **kwargs):
        """
        Handle POST request to register time.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the job id if registration is successful.
        """
        try:
            job_id = JobService.register_time(request.data, self.user)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        return Response({k_job_id: job_id}, status=HTTPStatus.OK)


class SignTimeRegistrationView(JWTBaseAuthView):
    """
    [CMS, Workers]

    POST

    A view to sign time registration.
    """

    app_types = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        """
        Handle POST request to sign time registration.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the time registration id if signing is successful.
        """
        try:
            time_registration_id = JobService.sign_time_registration(request.data)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        return Response({k_id: time_registration_id}, status=HTTPStatus.OK)


class ActiveJobList(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view to get active jobs.
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve active jobs.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of active jobs.
        """
        jobs = JobService.get_active_jobs()
        return Response({k_jobs: jobs})


class WorkersForJobView(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view for CMS users to get the workers of a job
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):

        try:
            job = Job.objects.get(id=kwargs["id"])
        except KeyError:
            return HttpResponseNotFound()

        applications = JobApplication.objects.filter(job_id=job.id)

        workers = []

        for application in applications:
            if application.application_state == JobApplicationState.approved:
                workers.append(WorkerUtil.to_worker_view(application.worker))

        registrations = []

        time_registrations = TimeRegistration.objects.filter(job_id=job.id)

        for time_registration in time_registrations:
            registrations.append(time_registration.to_model_view())

        return Response(
            {
                k_workers: workers,
                k_time_registrations: registrations,
            }
        )


class DoneJobList(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view to get done jobs.
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve done jobs.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of done jobs.
        """
        formatter = FormattingUtil(kwargs)
        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)
        jobs = JobService.get_done_jobs(start, end)
        return Response({k_jobs: jobs})


class DraftJobList(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view to get draft jobs.
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve draft jobs.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of draft jobs.
        """
        jobs = JobService.get_draft_jobs()
        return Response({k_jobs: jobs})


class ApplicationView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting application details.
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handle GET request to retrieve application details.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing application details.
        """
        try:
            application_data = JobApplicationService.get_application_details(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response(data=application_data)

    def delete(self, request: HttpRequest, *args, **kwargs):
        """
        Handle DELETE request to delete an application.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object indicating the result of the delete operation.
        """
        try:
            JobApplicationService.delete_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()


class ApproveApplicationView(JWTBaseAuthView):
    """
    [ALL]

    POST

    A view for approving applications.
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        """
        Handle POST request to approve an application.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object indicating the result of the approval operation.
        """
        try:
            JobApplicationService.approve_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()


class DenyApplicationView(JWTBaseAuthView):
    """
    [ALL]

    POST

    A view for denying applications.
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        """
        Handle POST request to deny an application.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object indicating the result of the denial operation.
        """
        try:
            JobApplicationService.deny_application(kwargs['id'])
        except KeyError:
            return HttpResponseNotFound()

        return Response()



class MyApplicationsView(JWTBaseAuthView):
    """
    [Workers]

    GET | POST

    A view for workers to view their applications and add new ones.
    """

    def get(self, request: HttpRequest):
        """
        Handle GET request to retrieve the worker's applications.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the list of applications.
        """
        application_model_list = JobApplicationService.get_my_applications(self.user)
        return Response({k_applications: application_model_list})

    def post(self, request: HttpRequest):
        """
        Handle POST request to create a new application.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            Response: A response object containing the application id if creation is successful.
        """
        try:
            application_id = JobApplicationService.create_application(request.data, self.user)
        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except ValueError as e:
            return Response({k_message: str(e)}, status=HTTPStatus.BAD_REQUEST)

        return Response({k_id: application_id})


class ApplicationsListView(JWTBaseAuthView):
    """
    [CMS]

    GET

    View for CMS users to get applications details.
    """

    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Handle GET request to retrieve the list of applications.

        Args:
            request (HttpRequest): The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: A response object containing the list of applications.
        """
        applications = JobApplicationService.get_applications_list(kwargs.get('job_id'))
        paginator = Paginator(applications, per_page=25)
        data = [application.to_model_view() for application in applications]

        return Response({k_applications: data, k_items_per_page: paginator.per_page, k_total: len(applications)})



class DirectionsView(JWTBaseAuthView):
    """
    View to handle fetching directions between two geographical points.
    Requires JWT authentication and user to be in specific groups.
    """
    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests to fetch directions.

        Args:
            request: The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments containing latitude and longitude.

        Returns:
            HttpResponse: The response containing directions if successful.
            HttpResponseBadRequest: The response if fetching directions fails.
        """
        # Extract and convert latitude and longitude from kwargs
        from_lat = int(kwargs.get('from_lat', 0)) / 1000000
        from_lon = int(kwargs.get('from_lon', 0)) / 1000000
        to_lat = int(kwargs.get('to_lat', 0)) / 1000000
        to_lon = int(kwargs.get('to_lon', 0)) / 1000000

        # Fetch directions using the JobApplicationService
        response = JobApplicationService.fetch_directions(from_lat, from_lon, to_lat, to_lon)

        # Return the response if directions are fetched successfully
        if response is not None:
            return HttpResponse(response)

        # Return a bad request response if fetching directions fails
        return HttpResponseBadRequest(response)

class ReverseGeocodeView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):

        query = None

        try:
            query = str(kwargs["query"])
        except KeyError:
            pass

        response = requests.get(
            url="{}/maps/api/geocode/json?latlng={}&key={}".format(
                settings.GOOGLE_BASE_URL,
                query,
                settings.GOOGLE_API_KEY,
            ),
        )

        if response.ok:
            return HttpResponse(
                response.content,
            )

        return HttpResponseBadRequest()
    



class GeocodeView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):

        query = None

        try:
            query = str(kwargs["query"])
        except KeyError:
            pass

        response = requests.get(
            url="{}/maps/api/geocode/json?address={}&key={}".format(
                settings.GOOGLE_BASE_URL,
                query,
                settings.GOOGLE_API_KEY,
            ),
        )

        if response.ok:
            return HttpResponse(
                response.content,
            )

        return HttpResponseBadRequest()
    



class AutocompleteView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WORKERS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):

        query = None

        try:
            query = str(kwargs["query"])
        except KeyError:
            pass

        response = requests.get(
            url="{}/maps/api/place/textsearch/json?input={}&region={}&key={}".format(
                settings.GOOGLE_BASE_URL,
                query,
                "be",
                settings.GOOGLE_API_KEY,

            ),
        )

        if response.ok:
            return HttpResponse(
                response.content,
            )

        return HttpResponseBadRequest()



class DimonaListView(JWTBaseAuthView):
    """
    [CMS]

    GET
    """

    # Overrides the app types with access to this view
    app_types = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        item_count = 25
        page = 1

        try:
            item_count = kwargs["count"]
            page = kwargs["page"]
        except KeyError:
            pass

        dimonas = Dimona.objects.all().order_by("-created")

        paginator = Paginator(dimonas, per_page=item_count)

        data = []

        for dimona in paginator.page(page).object_list:
            data.append(dimona.to_model_view())

        # Return the washer id
        return Response(
            {
                k_dimonas: data,
                k_items_per_page: paginator.per_page,
                k_total: len(dimonas),
            }
        )

class AdminStatisticsView(JWTBaseAuthView):
    """
    [CMS]

    GET

    A view for getting the admin statistics overview
    """

    app_types = [CMS_GROUP_NAME]

    def get(self, request: HttpRequest, *args, **kwargs):
        formatter = FormattingUtil(kwargs)
        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)

        if not start or not end:
            return HttpResponseNotFound()
        
        return Response(StatisticsService.get_admin_statistics(start, end))
    

class ExportsView(JWTBaseAuthView):
    """
    [CMS]

    GET | POST

    View for refreshing and getting exports
    """

    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        View for getting a list of all existing exports
        """

        item_count = 25
        page = 1
        sort_term = None
        algorithm = None

        try:
            item_count = kwargs["count"]
            page = kwargs["page"]
        except KeyError:
            pass
        try:
            sort_term = kwargs["sort_term"]
            algorithm = kwargs["algorithm"]
        except KeyError:
            pass

        if sort_term is not None:
            if algorithm == "descending":
                sort_term = "-{}".format(sort_term)

            export_files = ExportFile.objects.all().order_by(sort_term)

        else:
            export_files = ExportFile.objects.all().order_by("-created")

        paginator = Paginator(export_files, per_page=item_count)

        data = []

        for export in paginator.page(page).object_list:
            data.append(export.to_model_view())

        return Response(
            data={
                k_exports: data,
                k_items_per_page: paginator.per_page,
                k_total: len(
                    export_files,
                ),
            }
        )

    def post(self, request: HttpRequest):
        """
        Creates the latest monthly export
        """

        formatter = FormattingUtil(data=request.data)

        try:
            start = formatter.get_date(k_start_time)
            end = formatter.get_date(k_end_time)

        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response(
                {k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

        if start is None or end is None:
            start, end = ExportManager.get_last_month_period()

        ExportManager.create_time_registations_export(start, end)

        ExportManager.create_active_washers_export(start, end)

        return Response()
