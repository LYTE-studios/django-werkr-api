import datetime

from apps.core.model_exceptions import DeserializationException
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.managers.job_manager import JobManager
from apps.jobs.models import Job, JobApplication, JobApplicationState, JobState, TimeRegistration
from apps.jobs.utils.job_util import JobUtil
from apps.notifications.managers.notification_manager import NotificationManager
from apps.notifications.models.mail_template import CancelledMailTemplate, TimeRegisteredTemplate
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.jobs.models.tag import Tag
from apps.authentication.models.user import User


class JobService:

    @staticmethod
    def get_job_details(job_id):
        job = get_object_or_404(Job, id=job_id)
        return JobUtil.to_model_view(job)

    @staticmethod
    def delete_job(job_id):
        from apps.legal.services.link2prisma_service import Link2PrismaService

        job = get_object_or_404(Job, id=job_id)
        job.archived = True
        job.selected_workers = 0
        job.save(update_fields=['archived', 'selected_workers'])

        # Get approved applications before changing their state
        applications = JobApplication.objects.filter(job_id=job.id, application_state=JobApplicationState.approved)
        
        # Cancel Dimona declarations for all approved applications
        for application in applications:
            try:
                Link2PrismaService.handle_job_cancellation(application)
            except Exception as e:
                # Log error but don't prevent job deletion
                NotificationManager.notify_admin(
                    'Link2Prisma Job Cancellation Error',
                    f"Error cancelling Dimona declaration for job {job.id}, worker {application.worker.id}: {str(e)}"
                )

            NotificationManager.create_notification_for_user(
                application.worker, 'Your job got cancelled!', application.job.title, send_mail=False, image_url=None
            )

            CancelledMailTemplate().send(recipients=[{'Email': application.worker.email}],
                                       data={"job_title": application.job.title,})

        # Update application states after handling Dimona cancellations
        applications.update(application_state=JobApplicationState.rejected)

    @staticmethod
    def update_job(job_id, data):
        job = get_object_or_404(Job, id=job_id)
        formatter = FormattingUtil(data=data)
        current_max_workers = job.max_workers

        try:
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
            tag_id = formatter.get_value(k_tag_id)
        except DeserializationException as e:
            raise e
        except Exception as e:
            raise e

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
        if tag_id:
            try:
                tag = Tag.objects.get(id=tag_id)
                job.tag = tag
            except Tag.DoesNotExist:
                pass

        if job.max_workers > current_max_workers:
            JobManager.send_job_notification(job=job, title='New spot available!')

        job.save(update_fields=fields_to_update)

    @staticmethod
    def create_job(data):
        formatter = FormattingUtil(data=data)
        try:
            title = formatter.get_value(k_title, required=True)
            start_time = formatter.get_date(k_start_time, required=True)
            end_time = formatter.get_date(k_end_time, required=True)
            customer_id = formatter.get_value(k_customer_id, required=True)
            tag_id = formatter.get_value(k_tag_id, required=False)
            address = formatter.get_address(k_address, required=True)
            max_workers = formatter.get_value(k_max_workers, required=True)
            description = formatter.get_value(k_description)
            application_start_time = formatter.get_date(k_application_start_time)
            application_end_time = formatter.get_date(k_application_end_time)
            is_draft = formatter.get_bool(k_is_draft)
        except DeserializationException as e:
            raise e
        except Exception as e:
            raise e

        if tag_id:
            tag = get_object_or_404(Tag, id=tag_id)
        else: 
            customer = get_object_or_404(User, id=customer_id)
            tag = customer.customer_profile.tag
            

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
            is_draft=is_draft,
            tag=tag,
        )

        JobManager.create(job)
        return job.id

    @staticmethod
    def get_upcoming_jobs(user, is_worker=True, start=None, end=None):
        now = timezone.now()
        
        if is_worker:
            # Gets the current time
            current_time = timezone.now()

            # Query for upcoming jobs based on specified criteria
            jobs = Job.objects.filter(
                # The job must start in the future
                start_time__gt=current_time,
                # Ensure the application window is open
                application_start_time__lte=current_time,
                application_end_time__gte=current_time,
                selected_workers__lt=F('max_workers'),
                archived=False,
                tag__in=user.worker_profile.tags.all(),
            ).exclude(
                # Exclude jobs with Pending or Approved applications from the user
                jobapplication__worker=user,
                jobapplication__application_state__in=[JobApplicationState.pending, JobApplicationState.approved],
            ).exclude(
                # Exclude jobs that overlap with an already approved job of the user
                Q(
                    jobapplication__job__start_time__lt=F('end_time'),
                    jobapplication__job__end_time__gt=F('start_time'),
                    jobapplication__application_state=JobApplicationState.approved,
                    jobapplication__worker=user
                )
            ).distinct().order_by('start_time')

        else:
            if not start or not end:
                jobs = Job.objects.filter(
                    start_time__gt=now,
                    job_state=JobState.pending,
                    is_draft=False,
                    archived=False
                ).order_by('start_time')
            else:
                start = timezone.make_aware(start)
                end = timezone.make_aware(end)
                
                if start < now:
                    start = now
                jobs = Job.objects.filter( 
                    start_time__range=[start, end],
                    job_state=JobState.pending,
                    is_draft=False,
                    archived=False
                ).order_by('start_time')

        return [JobUtil.to_model_view(job) for job in jobs]
    
    @staticmethod
    def get_approved_jobs(user):
        return Job.objects.filter(
            job_state=JobState.pending,
            is_draft=False,
            archived=False,
            worker_id=user.id,
        ).order_by('start_time')

    @staticmethod
    def get_history_jobs(user, start, end):
        applications = JobApplication.objects.filter(
            job__start_time__lt=end,
            job__start_time__gt=start,
            worker_id=user.id,
            application_state=JobApplicationState.approved
        )[:50]

        return [JobUtil.to_model_view(application.job) for application in applications]

    @staticmethod
    def get_jobs_based_on_user(worker_id=None, customer_id=None):
        if worker_id and customer_id:
            jobs = Job.objects.filter(
                jobapplication__worker__id=worker_id,
                customer_id=customer_id,
                is_draft=False,
                archived=False
            )[:50]
        elif worker_id:
            jobs = Job.objects.filter(
                jobapplication__worker__id=worker_id,
                is_draft=False,
                archived=False
            )[:50]
        elif customer_id:
            jobs = Job.objects.filter(
                customer_id=customer_id,
                is_draft=False,
                archived=False
            )[:50]
        else:
            jobs = Job.objects.all()[:50]

        return [JobUtil.to_model_view(job) for job in jobs]

    @staticmethod
    def get_time_registrations(job_id):
        job = get_object_or_404(Job, id=job_id)
        times = TimeRegistration.objects.filter(job_id=job_id)
        return [time.to_model_view() for time in times]

    @staticmethod
    def register_time(data, user):
        formatter = FormattingUtil(data=data)
        
        job_id = formatter.get_value(k_job_id, required=True)
        start_time = FormattingUtil.to_date_time(int(formatter.get_value(k_start_time, required=True)))
        end_time = FormattingUtil.to_date_time(int(formatter.get_value(k_end_time, required=True)))
        break_time = formatter.get_time(k_break_time, required=False)
        worker_signature = data.get(k_worker_signature)
        customer_signature = data.get(k_customer_signature)

        job = get_object_or_404(Job, id=job_id)
        worker = user

        query = TimeRegistration.objects.filter(job_id=job_id, worker_id=worker.id)
        if query.exists():
            registration = query.first()
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

        TimeRegisteredTemplate().send(recipients=[{'Email': job.customer.email}], 
                                      data={"title": job.title, "interval": FormattingUtil.to_time_interval(start_time, end_time), "worker": user.get_full_name(),})

        time_registration_count = TimeRegistration.objects.filter(job_id=job.id).count()
        if time_registration_count >= job.selected_workers:
            job.job_state = JobState.done
            job.customer.save()
            job.save()

        return job.id

    @staticmethod
    def sign_time_registration(data):
        formatter = FormattingUtil(data=data)
        try:
            id = formatter.get_value(k_id, required=True)
            worker_signature = data.get(k_worker_signature)
            customer_signature = data.get(k_customer_signature)
        except Exception as e:
            raise e

        time_registration = get_object_or_404(TimeRegistration, id=id)
        time_registration.worker_signature = worker_signature
        time_registration.customer_signature = customer_signature
        time_registration.save()

        return time_registration.id

    @staticmethod
    def get_active_jobs():
        jobs = Job.objects.filter(
            job_state__in=[JobState.pending, JobState.fulfilled],
            start_time__lt=datetime.datetime.utcnow(),
            archived=False,
            is_draft=False
        ).order_by('start_time')[:50]

        jobs_model_list = []
        for job in jobs:
            if job.archived or job.selected_workers == 0:
                job.job_state = JobState.cancelled
                job.save()
                continue
            jobs_model_list.append(JobUtil.to_model_view(job))

        return jobs_model_list

    @staticmethod
    def get_done_jobs(start, end):
        if not start or not end:
            jobs = Job.objects.filter(
                job_state__in=[JobState.done, JobState.cancelled],
                archived=False
            ).order_by('-start_time')[:50]
        else:
            jobs = Job.objects.filter(
                job_state__in=[JobState.done, JobState.cancelled],
                archived=False,
                start_time__range=[start, end]
            ).order_by('-start_time')[:50]

        return [JobUtil.to_model_view(job) for job in jobs]

    @staticmethod
    def get_draft_jobs():
        jobs = Job.objects.filter(is_draft=True, archived=False)[:50]
        return [JobUtil.to_model_view(job) for job in jobs]
    
    @staticmethod
    def get_washer_job_history(worker_id, page=1, per_page=25):
        """
        Get paginated list of all approved jobs for a washer that haven't been deleted.
        
        Args:
            worker_id: ID of the worker
            page: Page number (default: 1)
            per_page: Number of items per page (default: 25)
            
        Returns:
            dict containing:
            - jobs: List of job model views
            - total: Total number of jobs
            - items_per_page: Number of items per page
        """
        jobs = JobApplication.objects.filter(
            worker__id=worker_id,
            application_state=JobApplicationState.approved,
            job__archived=False,
        ).order_by('-job__start_time').distinct()
        
        paginator = Paginator(jobs, per_page=per_page)
        
        try:
            paginated_jobs = paginator.page(page)
        except (EmptyPage, PageNotAnInteger):
            paginated_jobs = paginator.page(1)
            
        return {
            'applications': [job.to_model_view() for job in paginated_jobs],
            'total': jobs.count(),
            'items_per_page': per_page
        }

    @staticmethod
    def get_customer_job_history(customer_id, page=1, per_page=25):
        """
        Get paginated list of all jobs (including future jobs) for a customer.
        
        Args:
            customer_id: ID of the customer
            page: Page number (default: 1)
            per_page: Number of items per page (default: 25)
            
        Returns:
            dict containing:
            - jobs: List of job model views
            - total: Total number of jobs
            - items_per_page: Number of items per page
        """
        jobs = Job.objects.filter(
            customer_id=customer_id,
            archived=False
        ).order_by('-start_time')
        
        paginator = Paginator(jobs, per_page=per_page)
        
        try:
            paginated_jobs = paginator.page(page)
        except (EmptyPage, PageNotAnInteger):
            paginated_jobs = paginator.page(1)
            
        return {
            'jobs': [JobUtil.to_model_view(job) for job in paginated_jobs],
            'total': jobs.count(),
            'items_per_page': per_page
        }
