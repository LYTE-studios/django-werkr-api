from http import HTTPStatus

from django.http import HttpRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.db.models import F
from rest_framework.response import Response
from apps.authentication.views import JWTBaseAuthView
from .models import Job, JobApplication, JobApplicationState, JobState, TimeRegistration
from .utils.job_util import JobUtil
from apps.notifications.managers.notification_manager import NotificationManager
from apps.notifications.managers.mail_service_manager import MailServiceManager
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.notifications.models.mail_template import CancelledMailTemplate, TimeRegisteredTemplate
from apps.core.model_exceptions import DeserializationException
from apps.jobs.managers.job_manager import JobManager
from apps.core.assumptions import *
import datetime
import pytz


class JobView(JWTBaseAuthView):
    """
    [ALL]

    GET

    A view for getting job details
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        job = get_object_or_404(Job, id=kwargs['id'])
        return Response(data=JobUtil.to_model_view(job))

    def delete(self, request: HttpRequest, *args, **kwargs):
        try:
            job = Job.objects.get(id=kwargs['id'])
        except (KeyError, Job.DoesNotExist):
            return HttpResponseNotFound()

        job.archived = True
        job.selected_workers = 0
        job.save(update_fields=['archived', 'selected_workers'])

        applications = JobApplication.objects.filter(job_id=job.id, application_state=JobApplicationState.approved)
        applications.update(application_state=JobApplicationState.rejected)

        for application in applications:
            NotificationManager.create_notification_for_user(
                application.worker, 'Your job got cancelled!', application.job.title, send_mail=False, image_url=None
            )
            MailServiceManager.send_template(application.worker, CancelledMailTemplate(), data={
                "job_title": application.job.title,
            })

        return Response()

    def put(self, request: HttpRequest, *args, **kwargs):
        job = get_object_or_404(Job, id=kwargs['id'])
        formatter = FormattingUtil(data=request.data)

        try:
            # Optional fields
            title = formatter.get_value(k_title)
            start_time = formatter.get_date(k_start_time)
            end_time = formatter.get_date(k_end_time)
            customer_id = formatter.get_value(k_customer_id)
            address = formatter.get_address(k_address)
            max_workers = formatter.get_value(k_max_workers)
            description = formatter.get_value(k_description)
            application_start_time = formatter.get_date(k_application_start_time)
            application_end_time = formatter.get_date(k_application_end_time)
            is_draft = formatter.get_bool(k_is_draft)

        except DeserializationException as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        fields_to_update = []
        if title:
            job.title = title
            fields_to_update.append('title')
        if start_time:
            job.start_time = start_time
            fields_to_update.append('start_time')
        if end_time:
            job.end_time = end_time
            fields_to_update.append('end_time')
        if customer_id:
            job.customer_id = customer_id
            fields_to_update.append('customer_id')
        if address:
            job.address = address
            address.save()
            fields_to_update.append('address')
        if max_workers:
            job.max_workers = max_workers
            fields_to_update.append('max_workers')
        if description:
            job.description = description
            fields_to_update.append('description')
        if application_start_time:
            job.application_start_time = application_start_time
            fields_to_update.append('application_start_time')
        if application_end_time:
            job.application_end_time = application_end_time
            fields_to_update.append('application_end_time')
        if is_draft is not None:
            job.is_draft = is_draft
            fields_to_update.append('is_draft')

        job.save(update_fields=fields_to_update)

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

        formatter = FormattingUtil(data=request.data)
        try:
            # Required fields
            title = formatter.get_value(k_title, required=True)
            start_time = formatter.get_date(k_start_time, required=True)
            end_time = formatter.get_date(k_end_time, required=True)
            customer_id = formatter.get_value(k_customer_id, required=True)
            address = formatter.get_address(k_address, required=True)
            max_workers = formatter.get_value(k_max_workers, required=True)

            # Optional fields
            description = formatter.get_value(k_description)
            application_start_time = formatter.get_date(k_application_start_time)
            application_end_time = formatter.get_date(k_application_end_time)
            is_draft = formatter.get_bool(k_is_draft)

        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        job = Job(
            customer_id=customer_id,
            title=title,
            description=description,
            address=address,
            job_state=JobState.pending,
            start_time=start_time,
            end_time=end_time,
            application_start_time=application_start_time,
            application_end_time=application_end_time,
            max_workers=max_workers,
            selected_workers=0,
            is_draft=is_draft
        )

        JobManager.create(job)

        return Response({k_job_id: job.id, })


class UpcomingJobsView(JWTBaseAuthView):
    """
    [Workers]

    GET

    A view for workers to get their upcoming jobs
    """

    groups = [
        WASHERS_GROUP_NAME,
    ]

    def is_available_to_user(self, job: Job):
        if JobApplication.objects.filter(worker_id=self.user.id, job_id=job.id,
                                         application_state__in=[JobApplicationState.approved,
                                                                JobApplicationState.pending]).exists():
            return False

        date_range = [job.start_time - datetime.timedelta(hours=3),
                      job.end_time + datetime.timedelta(hours=3)]

        before_check = JobApplication.objects.filter(worker=self.user, job__start_time__range=date_range,
                                                     application_state=JobApplicationState.approved).exists()
        after_check = JobApplication.objects.filter(worker=self.user, job__end_time__range=date_range,
                                                    application_state=JobApplicationState.approved).exists()

        return not (before_check or after_check)

    def get(self, request: HttpRequest):
        data = []

        jobs = Job.objects.filter(start_time__gte=datetime.datetime.now(),
                                  application_start_time__lte=datetime.datetime.now(),
                                  application_end_time__gte=datetime.datetime.now(),
                                  job_state=JobState.pending,
                                  selected_workers__lt=F('max_workers'),
                                  is_draft=False,
                                  archived=False).order_by('start_time')[:50]

        for job in jobs:
            if self.is_available_to_user(job=job):
                data.append(job)

        job_model_list = [JobUtil.to_model_view(job) for job in data]

        return Response({k_jobs: job_model_list})


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

        data = []

        if not start or not end:
            jobs = Job.objects.filter(start_time__gt=datetime.datetime.utcnow(), job_state=JobState.pending,
                                      is_draft=False,
                                      archived=False).order_by('start_time')[:50]
        else:
            now = pytz.utc.localize(datetime.datetime.utcnow())

            if start < now:
                start = now

            jobs = Job.objects.filter(start_time__range=[start, end], job_state=JobState.pending,
                                      is_draft=False,
                                      archived=False).order_by('start_time')[:50]

        for job in jobs:
            data.append(JobUtil.to_model_view(job))

        return Response({k_jobs: data})


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

        applications = JobApplication.objects.filter(job__start_time__lt=end, job__start_time__gt=start,
                                                     worker_id=self.user.id,
                                                     application_state=JobApplicationState.approved)[:50]

        job_model_list = [JobUtil.to_model_view(application.job) for application in applications]

        return Response({k_jobs: job_model_list})


class GetJobsBasedOnUserView(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME,
        CUSTOMERS_GROUP_NAME,
    ]

    def post(self, request, *args, **kwargs):
        # Assuming the body of the request is in JSON format
        formatter = FormattingUtil(data=request.data)

        try:
            worker_id = formatter.get_value(k_worker_id)
            customer_id = formatter.get_value(k_customer_id)
        except DeserializationException as e:
            # If the inner validation fails, this throws an error
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)
        except Exception as e:
            # Unhandled exception
            return Response({k_message: e.args}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

        if worker_id and customer_id:
            jobs = Job.objects.filter(jobapplication__worker__id=worker_id, customer_id=customer_id, is_draft=False,
                                      archived=False)[:50]
        elif worker_id:
            jobs = Job.objects.filter(jobapplication__worker__id=worker_id, is_draft=False, archived=False)[:50]
        elif customer_id:
            jobs = Job.objects.filter(customer_id=customer_id, is_draft=False, archived=False)[:50]
        else:
            jobs = Job.objects.all()[:50]

        jobs_model_list = [JobUtil.to_model_view(job) for job in jobs]

        return Response({k_jobs: jobs_model_list})


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

        job = Job.objects.get(id=job_id)

        if job:
            times = TimeRegistration.objects.filter(job_id=job_id)
        else:
            return Response({k_message: 'Job id is required'}, status=HTTPStatus.BAD_REQUEST)

        times_model_list = [time.to_model_view() for time in times]

        return Response({k_times: times_model_list})

    def post(self, request: HttpRequest, *args, **kwargs):
        formatter = FormattingUtil(data=request.data)

        worker = None

        worker_signature = None
        customer_signature = None

        try:
            worker = User.objects.get(id=kwargs[k_user_id])
        except KeyError:
            pass
        except User.DoesNotExist:
            return Response(status=HTTPStatus.BAD_REQUEST)

        try:
            job_id = formatter.get_value(k_job_id, required=True)
            start_time = FormattingUtil.to_date_time(int(formatter.get_value(k_start_time, required=True)))
            end_time = FormattingUtil.to_date_time(int(formatter.get_value(k_end_time, required=True)))
            break_time = formatter.get_time(k_break_time, required=False)

            try:
                # Signatures are optional in this view
                worker_signature = request.FILES[k_worker_signature]
                customer_signature = request.FILES[k_customer_signature]
            except KeyError:
                pass
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        job = Job.objects.get(id=job_id)

        if job is None:
            return Response({k_message: 'Job not found'}, status=HTTPStatus.BAD_REQUEST)

        if worker is None:
            worker = self.user

        query = TimeRegistration.objects.filter(job_id=job_id, worker_id=worker.id)

        if query.exists():
            registration = query.first()

            job.customer.hours -= (registration.start_time - registration.end_time).seconds / 3600

            job.customer.save()

            registration.delete()

        time_registration = TimeRegistration(
            job=job,
            start_time=start_time,
            end_time=end_time,
            break_time=break_time,
            worker=worker,
            worker_signature=worker_signature,
            customer_signature=customer_signature,
        )

        time_registration.save()

        # Customer email
        MailServiceManager.send_template(job.customer, TimeRegisteredTemplate(), {
            "title": job.title,
            "interval": FormattingUtil.to_time_interval(start_time, end_time),
            "worker": self.user.get_full_name(),
        })

        application = JobApplication.objects.filter(job_id=job_id, worker_id=worker.id).first()

        time_registration_count = TimeRegistration.objects.filter(job_id=job.id).count()

        if time_registration_count >= job.selected_workers:
            job.job_state = JobState.done

            job.customer.hours += (time_registration.start_time - time_registration.end_time).seconds / 3600

            job.customer.save()

            job.save()

        return Response({k_job_id: job_id}, status=HTTPStatus.OK)


class SignTimeRegistrationView(JWTBaseAuthView):
    app_types = [
        CMS_GROUP_NAME,
        WASHERS_GROUP_NAME,
    ]

    def post(self, request: HttpRequest):
        formatter = FormattingUtil(data=request.data)
        try:
            id = formatter.get_value(k_id, required=True)
            # Signatures are optional in this view
            worker_signature = request.FILES[k_worker_signature]
            customer_signature = request.FILES[k_customer_signature]
        except Exception as e:
            return Response({k_message: e.args}, status=HTTPStatus.BAD_REQUEST)

        time_registration = TimeRegistration.objects.get(id=id)

        time_registration.worker_signature = worker_signature
        time_registration.customer_signature = customer_signature

        time_registration.save()

        return Response({k_id: time_registration.id}, status=HTTPStatus.OK)


class ActiveJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        jobs = Job.objects.filter(job_state__in=[JobState.pending, JobState.fulfilled],
                                  start_time__lt=datetime.datetime.utcnow(),
                                  archived=False, is_draft=False).order_by('start_time')[:50]

        jobs_model_list = []

        for job in jobs:
            def cancel_job():
                job.job_state = JobState.cancelled
                job.save()

            if job.archived or job.selected_workers == 0:
                cancel_job()
                continue

            jobs_model_list.append(JobUtil.to_model_view(job))

        return Response({k_jobs: jobs_model_list})


class DoneJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        formatter = FormattingUtil(kwargs)

        start = formatter.get_date(value_key=k_start)
        end = formatter.get_date(value_key=k_end)

        if not start or not end:
            jobs = Job.objects.filter(job_state__in=[JobState.done, JobState.cancelled], archived=False).order_by(
                '-start_time')[:50]
        else:
            jobs = Job.objects.filter(job_state__in=[JobState.done, JobState.cancelled], archived=False,
                                      start_time__range=[start, end]).order_by('-start_time')[:50]

        jobs_model_list = [JobUtil.to_model_view(job) for job in jobs]

        return Response({k_jobs: jobs_model_list})


class DraftJobList(JWTBaseAuthView):
    groups = [
        CMS_GROUP_NAME,
    ]

    def get(self, request, *args, **kwargs):
        jobs = Job.objects.filter(is_draft=True, archived=False)[:50]

        jobs_model_list = [JobUtil.to_model_view(job) for job in jobs]

        return Response({k_jobs: jobs_model_list})