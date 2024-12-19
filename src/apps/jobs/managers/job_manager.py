import datetime

from django.db import models
from django.template.loader import get_template
import os
import io

from itertools import chain
from django.core.files import File
from apps.core.utils.formatters import FormattingUtil
from apps.jobs.models import JobApplication, Job, JobApplicationState
from apps.notifications.managers.mail_service_manager import MailServiceManager
from apps.notifications.managers.notification_manager import NotificationManager, create_global_notification
from apps.notifications.models import ApprovedMailTemplate, DeniedMailTemplate, SelectedWorkerTemplate


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

        MailServiceManager.send_template(application.worker, DeniedMailTemplate(), {
            "job_title": job.title,
            "city": job.address.city or 'Belgium',
        })

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
        MailServiceManager.send_template(application.worker, ApprovedMailTemplate(), {
            "job_title": job.title,
            "weekday": FormattingUtil.to_day_of_the_week(start),
            "date": FormattingUtil.to_date(start),
            "time_interval": FormattingUtil.to_time_interval(start, end),
            "customer_name": job.customer.get_full_name(),
            "address": job.address.to_readable(),
        })

        # Worker notification
        NotificationManager.create_notification_for_user(application.worker,
                                                         'Approved job - {}'.format(job.title),
                                                         'You\'ve been approved by an admin for a job in {}'.format(
                                                             job.address.city or job.address.country or 'Belgium'),
                                                         image_url=None,
                                                         send_mail=False, )

        # Customer email
        MailServiceManager.send_template(application.job.customer, SelectedWorkerTemplate(), {
            "title": job.title,
            "weekday": FormattingUtil.to_day_of_the_week(start),
            "date": FormattingUtil.to_date(start),
            "interval": FormattingUtil.to_readable_time(start),
            "worker": application.worker.first_name,
            "address": job.address.to_readable(),
        })

    @staticmethod
    def approve_application(application: JobApplication):

        application.application_state = JobApplicationState.approved

        JobManager._notify_approved_worker(application)

        # JobManager.generate_contract(application)
        JobManager.remove_overlap_applications(application)
        JobManager.calculate_selected_workers(application)

        application.save()

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

        create_global_notification.delay(title, description, image_url=None, send_push=True)

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

    @staticmethod
    def generate_contract(application: JobApplication):
        start = FormattingUtil.to_user_timezone(application.job.start_time)
        end = FormattingUtil.to_user_timezone(application.job.end_time)

        start_time_morning = ''
        end_time_morning = ''

        start_time_afternoon = ''
        end_time_afternoon = ''

        if start.hour < 12:
            start_time_morning = FormattingUtil.to_readable_time(application.job.start_time)
            if end.hour < 12:
                end_time_morning = FormattingUtil.to_readable_time(application.job.end_time)
            else:
                end_time_morning = '12:00'
        else:
            start_time_afternoon = FormattingUtil.to_readable_time(application.job.start_time)
            end_time_afternoon = FormattingUtil.to_readable_time(application.job.end_time)

        weekday = FormattingUtil.to_day_of_the_week(application.job.start_time)

        start_date = FormattingUtil.to_date(application.job.start_time)
        end_date = FormattingUtil.to_date(application.job.end_time)
        duration = FormattingUtil.to_readable_duration(application.job.end_time - application.job.start_time, )

        name = application.worker.first_name + " " + application.worker.last_name

        address = ''

        if application.worker.address is not None:
            address = application.worker.address.to_readable()

        birth_date = None

        if application.worker.date_of_birth is not None:
            birth_date = FormattingUtil.to_full_date(application.worker.date_of_birth)

        template = get_template('contract_template.html')

        html = template.render({
            'name': name,
            'address': address,
            'birth_date': birth_date,
            'iban': application.worker.tax_number,

            'weekday': weekday,
            'start_date': start_date,
            'end_date': end_date,
            'start_time_morning': start_time_morning,
            'end_time_morning': end_time_morning,
            'start_time_afternoon': start_time_afternoon,
            'end_time_afternoon': end_time_afternoon,
            'duration': duration,
        })

        file_name = 'day_contract_{}_{}.pdf'.format(application.id,
                                                    str(FormattingUtil.to_timestamp(datetime.datetime.now())))

        temp_file = open(file_name, 'w+b')

        os.remove(file_name)

        return

        bytes = File(generate_pdf(html.encode('utf-8'), dest=temp_file, encoding='utf-8'))

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception('File not created')

        application.contract = file

        application.save()
