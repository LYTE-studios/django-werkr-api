import datetime

from django.db import models

from itertools import chain
from apps.core.utils.formatters import FormattingUtil
from apps.jobs.models import JobApplication, Job, JobApplicationState
from apps.notifications.managers.notification_manager import NotificationManager, create_global_notification
from apps.notifications.models import ApprovedMailTemplate, DeniedMailTemplate, SelectedWorkerTemplate
from apps.legal.services.dimona_service import DimonaService
from apps.legal.utils.contract_util import ContractUtil


class JobManager(models.Manager):

    """
    This class manages operations related to job applications, such as sending notifications, 
    updating job application state, handling scheduling conflicts and generating contracts.


    Each static method is documented with its purpose, parameters and returns values.
    """

    @staticmethod
    def deny_application(application: JobApplication, send_notifications: bool = True) -> None:
        """
        Handles the denial of a job application by updating its state, notifying the worker and managing related services.

        Args:
        Application (JobApplication): The job application being denied.
        send_notifications (bool): Whether to send notifications to the worker. Defaults to True.
        """
        # Store the original state before making changes
        was_pending = application.application_state == JobApplicationState.pending

        send_new_push = application.job.max_workers - application.job.selected_workers == 0

        application.application_state = JobApplicationState.rejected
        application.save()

        job = application.job
        selected_workers = JobManager.calculate_selected_workers(application)

        if (job.max_workers - selected_workers) > 0 and send_new_push:
            JobManager._send_job_notification(job=job, title='New spot available!')

        DimonaService.cancel_dimona(application)
        
        # Only send notifications if explicitly requested AND the application was pending before
        if send_notifications and was_pending:
            DeniedMailTemplate().send(recipients=[{'Email': application.worker.email}], data={"job_title": job.title, "city": job.address.city or 'Belgium'})
            NotificationManager.create_notification_for_user(application.worker, 'Job full! - {}'.format(job.title), 'You weren\'t selected for a job you applied to!', image_url=None, send_mail=False)

    @staticmethod
    def _notify_approved_worker(application: JobApplication) -> None:
        """
        Handles the approval of a job application by notifying the worker.

        Args:
        Application (JobApplication): The job application being approved.

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
                                            "worker": application.worker.first_name or "", "address": job.address.to_readable(), "phone_number": application.worker.phone_number or "", })


    @staticmethod
    def approve_application(application: JobApplication) -> None:

        """
        Processes job application approval by performing the following steps:

        - Creates a Dimona declaration using DimonaService.create_dimona.
        - Updates the application state to 'approved'.
        - Sends a notification to the worker about the approval.
        - Rejects overlapping applications to prevent scheduling conflicts.
        - Updates the count of selected workers for the job.
        - Generates a contract PDF using ContractUtil.generate_contract.

        Args:
        application (JobApplication): The job application to approve.
        """

        DimonaService.create_dimona(application)

        application.application_state = JobApplicationState.approved

        JobManager._notify_approved_worker(application)

        JobManager.remove_overlap_applications(application)
        JobManager.calculate_selected_workers(application)

        application.save()

        try:
            ContractUtil.generate_contract(application)
        except Exception as e:
            print(e)
            pass
    @staticmethod
    def remove_unselected_workers(job: Job) -> None:
        """Rejects pending applications and notifies workers."""
        pending = JobApplication.objects.filter(job_id=job.id, application_state=JobApplicationState.pending)
        for app in pending:
            JobManager.deny_application(app, send_notifications=False)
            DeniedMailTemplate().send(recipients=[{'Email': app.worker.email}], data={"job_title": job.title, "city": job.address.city or 'Belgium'})
            NotificationManager.create_notification_for_user(app.worker, 'Job full! - {}'.format(job.title), 'You weren\'t selected for a job you applied to!', image_url=None, send_mail=False)

    @staticmethod
    def calculate_selected_workers(application: JobApplication):
        
        """
        Updates the count of selected workers for a job.
        This function calculates the number of approved applications for a job and updates the selected_workers.
        If the job reaches the maximum numbers of workers, it rejects the remaining pending.

        Args:
        application (JobApplication): The job application being processed.

        Returns:
        int : updated nnumber of selected workers for a job
        """
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
        
        """
        Processes the job application by saving the worker's address and application.

        Args:
        application (JobApplication): The job application to be processed.

        Returns:
        JobApplication: The processed job application.
        """
        application.address.save()

        application.save()

        return application

    @staticmethod
    def _send_job_notification(job: Job, title: str = 'New job available!', ) -> None:
        
        """
        Handles notifications to workers about a new job.
        This function formats the job's start time and location, then creates 
        a global notification for workers, with the provided title and a description 
        containing the job's location, date, and time.

        Args:
        job (Job): The job for which the notification is being sent.
        title (str): The title of the notification
        """

        # Format the date time values
        date = FormattingUtil.to_date(job.start_time)
        time = FormattingUtil.to_readable_time(job.start_time)

        city = job.address.city or job.address.country or 'Belgium'

        description = 'in {} on {} at {}'.format(city, date, time, )

        create_global_notification(title, description, image_url=None, send_push=True)

    @staticmethod
    def get_overlap_applications(application: JobApplication, state: JobApplicationState = JobApplicationState.pending):
        
        """
        Retrieves job applications that overlap with the start time of the specified application for the same worker.

        The function checks for applications that fall within a 3-hour buffer before and after the 
        start and end time of the job associated with the provided application. This allows the system 
        to account for potential scheduling conflicts.

        Args:
        application (JobApplication): The job application for which overlapping applications are checked.
        state (JobApplicationState): The state of the application to filter by. Defaults to 'pending'.
    
        Returns:
        QuerySet: A queryset of JobApplication objects for the same worker that overlap with the specified 
                  application's job start time within the 3-hour buffer.
        """

        date_range = [application.job.start_time - datetime.timedelta(hours=3),
                      application.job.end_time + datetime.timedelta(hours=3)]

        overlap_applications = JobApplication.objects.filter(worker_id=application.worker_id,
                                                             job__start_time__range=date_range,
                                                             application_state=state, )
        return overlap_applications

    @staticmethod
    def get_end_overlap_applications(application: JobApplication,
                                     state: JobApplicationState = JobApplicationState.pending):
        

        """
        Retrieves job applications for the worker that overlap with the end time of the specified job application.
    
        This method looks for applications that are in the same state (default is 'pending') and whose job's 
        end time falls within a 3-hour buffer before and after the job's end time. The function is used to 
        prevent scheduling conflicts with jobs.

        Args:
        application (JobApplication): The job application for which overlapping applications are checked.
        state (JobApplicationState): The state of the job applications to filter by (default is 'pending').

        Returns:
        QuerySet: A queryset of JobApplication objects for the same worker that overlap with the specified 
                  application's job end time within the 3-hour buffer.
        """
        

        date_range = [application.job.start_time - datetime.timedelta(hours=3),
                      application.job.end_time + datetime.timedelta(hours=3)]

        overlap_applications = JobApplication.objects.filter(worker_id=application.worker_id,
                                                             job__end_time__range=date_range,
                                                             application_state=state, )
        return overlap_applications

    @staticmethod
    def remove_overlap_applications(application: JobApplication) -> None:
        
        """
        Rejects overlapping job applications for the same worker to prevent scheduling conflicts.

        This method checks for job applications that overlap with the specified application. It retrieves both 
        the applications that overlap with the job's start time and the ones that overlap with the job's end time.
        Any overlapping applications that are not already rejected will have their state updated to 'rejected', 
        ensuring that the worker is not scheduled for conflicting jobs.

        Args:
        application (JobApplication): The job application whose overlaps are to be checked and removed.
        """

        overlap_applications = JobManager.get_overlap_applications(application)
        end_overlap_applications = JobManager.get_end_overlap_applications(application)

        applications = set(chain(overlap_applications, end_overlap_applications))

        for overlap_application in applications:
            if overlap_application.application_state != JobApplicationState.rejected:
                overlap_application.application_state = JobApplicationState.rejected
            overlap_application.save()

    @staticmethod
    def create(job: Job):
        
        """
        Creates a new job, initializes its selected workers count, saves the job's address, and sends a
        notification if the job is visible and not a draft.

        This method performs the following tasks:
        - Sets the selected_workers to 0 by default.
        - Saves the job's address.
        - Saves the job itself.
        - If the job is visible and not a draft, sends a notification to workers.

        Args:
        job (Job): The job object to be created.

        Returns:
        Job: The created job object.
        """
        job.selected_workers = 0

        job.address.save()

        job.save()

        # Only send notification if the job is not a draft
        if not job.is_draft:
            JobManager._send_job_notification(job)

        return job
