import datetime

from django.db import models
import asyncio

from itertools import chain
from django.core.files import File
from apps.core.utils.formatters import FormattingUtil
from apps.jobs.models import JobApplication, Job, JobApplicationState
from apps.notifications.managers.notification_manager import NotificationManager, create_global_notification
from apps.notifications.models import ApprovedMailTemplate, DeniedMailTemplate, SelectedWorkerTemplate
from apps.legal.services.dimona_service import DimonaService
from apps.legal.utils.contract_util import ContractUtil



class JobManager(models.Manager):

    @staticmethod
    def deny_application(application: JobApplication):

        send_new_push = application.job.max_workers - application.job.selected_workers == 0

        application.application_state = JobApplicationState.rejected

        application.save()

        job = application.job

        selected_workers = JobManager.calculate_selected_workers(application)

        if (job.max_workers - selected_workers) > 0 and send_new_push:
            JobManager._send_job_notification(job=job, title='New spot available!', )

        DimonaService.cancel_dimona(application)
        
        DeniedMailTemplate().send(recipients=[{'Email': application.worker.email}], 
                                  data={"job_title": job.title, "city": job.address.city or 'Belgium',})

        NotificationManager.create_notification_for_user(application.worker,
                                                         'Job full! - {}'.format(job.title),
                                                         'You weren\'t selected for a job you applied to!',
                                                         image_url=None,
                                                         send_mail=False, )

    @staticmethod
    def _notify_approved_worker(application: JobApplication):
        """
        Send the worker and customer the correct notifications for the approval
        """

        # The corresponding job
        job = application.job

        # Start - End times
        start = job.start_time
        end = job.end_time

        # Worker email
        ApprovedMailTemplate().send(recipients=[{'Email': application.worker.email}], 
                                    data={"job_title": job.title, "weekday": FormattingUtil.to_day_of_the_week(start), 
                                          "date": FormattingUtil.to_date(start), "time_interval": FormattingUtil.to_time_interval(start, end), 
                                          "customer_name": job.customer.get_full_name(), "address": job.address.to_readable(),})

        # Worker notification
        NotificationManager.create_notification_for_user(application.worker,
                                                         'Approved job - {}'.format(job.title),
                                                         'You\'ve been approved by an admin for a job in {}'.format(
                                                             job.address.city or job.address.country or 'Belgium'),
                                                         image_url=None,
                                                         send_mail=False, )

        # Customer email
        SelectedWorkerTemplate().send(recipients=[{'Email': application.job.customer.email}],   
                                      data={"title": job.title, "weekday": FormattingUtil.to_day_of_the_week(start), 
                                            "date": FormattingUtil.to_date(start), "interval": FormattingUtil.to_readable_time(start), \
                                            "worker": application.worker.first_name, "address": job.address.to_readable(),})


    @staticmethod
    def approve_application(application: JobApplication):

        DimonaService.create_dimona(application)

        application.application_state = JobApplicationState.approved

        JobManager._notify_approved_worker(application)

        JobManager.remove_overlap_applications(application)
        JobManager.calculate_selected_workers(application)

        application.save()

        ContractUtil.generate_contract(application)

    @staticmethod
    def remove_unselected_workers(job: Job):
        applications = JobApplication.objects.filter(job_id=job.id, application_state=JobApplicationState.pending)

        for application in applications:
            JobManager.deny_application(application)

    @staticmethod
    def calculate_selected_workers(application: JobApplication):
        application.save()

        count = JobApplication.objects.filter(job_id=application.job.id,
                                              application_state=JobApplicationState.approved).count()

        if application.job.selected_workers != count:
            application.job.selected_workers = count

            application.job.save()

        if application.job.selected_workers >= application.job.max_workers:
            JobManager.remove_unselected_workers(application.job)

        return count

    @staticmethod
    def apply(application: JobApplication):
        application.address.save()

        application.save()

        return application

    @staticmethod
    def _send_job_notification(job: Job, title: str = 'New job available!', ):
        # Format the date time values
        date = FormattingUtil.to_date(job.start_time)
        time = FormattingUtil.to_readable_time(job.start_time)

        city = job.address.city or job.address.country or 'Belgium'

        description = 'in {} on {} at {}'.format(city, date, time, )

        create_global_notification(title, description, image_url=None, send_push=True)

    @staticmethod
    def get_overlap_applications(application: JobApplication, state: JobApplicationState = JobApplicationState.pending):
        date_range = [application.job.start_time - datetime.timedelta(hours=3),
                      application.job.end_time + datetime.timedelta(hours=3)]

        overlap_applications = JobApplication.objects.filter(worker_id=application.worker_id,
                                                             job__start_time__range=date_range,
                                                             application_state=state, )
        return overlap_applications

    @staticmethod
    def get_end_overlap_applications(application: JobApplication,
                                     state: JobApplicationState = JobApplicationState.pending):
        date_range = [application.job.start_time - datetime.timedelta(hours=3),
                      application.job.end_time + datetime.timedelta(hours=3)]

        overlap_applications = JobApplication.objects.filter(worker_id=application.worker_id,
                                                             job__end_time__range=date_range,
                                                             application_state=state, )
        return overlap_applications

    @staticmethod
    def remove_overlap_applications(application: JobApplication):
        overlap_applications = JobManager.get_overlap_applications(application)
        end_overlap_applications = JobManager.get_end_overlap_applications(application)

        applications = set(chain(overlap_applications, end_overlap_applications))

        for overlap_application in applications:
            if overlap_application.application_state != JobApplicationState.rejected:
                overlap_application.application_state = JobApplicationState.rejected
            overlap_application.save()

    @staticmethod
    def create(job: Job):
        job.selected_workers = 0

        job.address.save()

        job.save()

        if job.is_visible():
            JobManager._send_job_notification(job)

        return job
