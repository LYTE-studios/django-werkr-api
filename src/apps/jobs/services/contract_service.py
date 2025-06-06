import datetime

import requests
from apps.authentication.models import FavoriteAddress
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.jobs.job_exceptions import JobNotFoundException
from django.db.models import F, Q

from apps.jobs.models.stored_directions import StoredDirections
from apps.jobs.managers.job_manager import JobManager
from apps.jobs.models import JobApplication, JobApplicationState, Job, JobState
from django.shortcuts import get_object_or_404

from apps.authentication.utils.worker_util import WorkerUtil
from rest_framework.exceptions import ValidationError



class JobApplicationService:

    @staticmethod
    def get_application_details(application_id):
        application = get_object_or_404(JobApplication, id=application_id)
        return application.to_model_view()

    @staticmethod
    def delete_application(application_id):
        application = get_object_or_404(JobApplication, id=application_id)
        application.application_state = JobApplicationState.rejected
        application.save()

    @staticmethod
    def approve_application(application_id):
        """
        Approves the job application if the worker's profile is 100% complete.
        Also creates a Dimona declaration in Link2Prisma.

        Args:
            application_id (int): The ID of the job application to approve.

        Raises:
            ValidationError: If the worker's profile is incomplete (less than 100%).
        """
        from apps.legal.services.link2prisma_service import Link2PrismaService

        application = get_object_or_404(JobApplication, id=application_id)
        worker = application.worker
        
        # Validate worker's profile before approval
        completion_data = WorkerUtil.calculate_worker_completion(worker)
        completion_percentage = completion_data[0]
        missing_fields = completion_data[1]

        if completion_percentage < 100:
            raise ValidationError(
                f"Cannot approve application. Profile is incomplete. "
                f"Completion percentage: {completion_percentage}%. Missing fields: {', '.join(missing_fields)}"
            )

        # If the profile is completed, proceed with approval
        JobManager.approve_application(application)
        application.job.save()
        application.save()

        # Create Dimona declaration in Link2Prisma
        try:
            Link2PrismaService.handle_job_approval(application)
        except Exception as e:
            # Log error but don't prevent approval
            from apps.notifications.managers.notification_manager import NotificationManager
            NotificationManager.notify_admin(
                'Link2Prisma Job Approval Error',
                f"Error creating Dimona declaration: {str(e)}"
            )

    @staticmethod
    def deny_application(application_id):
        """
        Denies the job application and cancels any existing Dimona declaration.
        """
        from apps.legal.services.link2prisma_service import Link2PrismaService

        application = get_object_or_404(JobApplication, id=application_id)
        old_state = application.application_state
        
        JobManager.deny_application(application)
        application.job.save()
        application.save()

        # If application was previously approved, cancel Dimona declaration
        if old_state == JobApplicationState.approved:
            try:
                Link2PrismaService.handle_job_cancellation(application)
            except Exception as e:
                # Log error but don't prevent denial
                from apps.notifications.managers.notification_manager import NotificationManager
                NotificationManager.notify_admin(
                    'Link2Prisma Job Cancellation Error',
                    f"Error cancelling Dimona declaration: {str(e)}"
                )

    @staticmethod
    def fetch_directions(lat, lon, to_lat, to_lon):

        import json

        stored_directions = StoredDirections.objects.filter(
            Q(from_lat=lat) & Q(from_lon=lon) & Q(to_lat=to_lat) & Q(to_lon=to_lon)
        ).first()

        if stored_directions and not stored_directions.check_expired():
            return stored_directions.directions_response
        
        else: 
            from django.conf import settings
            response = requests.post(
                url='{}/directions/v2:computeRoutes'.format(settings.GOOGLE_ROUTES_URL),
                headers={
                    "X-Goog-Api-Key": settings.GOOGLE_API_KEY,
                    "X-Goog-FieldMask": "routes.distanceMeters,routes.polyline",
                },
                json={
                    "origin": {
                        "location": {
                            "latLng": {
                                "latitude": lat,
                                "longitude": lon
                            }   
                        }
                    },
                "destination": {
                    "location": {
                        "latLng": {
                            "latitude": to_lat,
                            "longitude": to_lon,
                        }
                    }
                },
                "travelMode": "DRIVE",
                },
            )

            if response.ok:
                directions_response = json.dumps(response.json())

                StoredDirections(
                    from_lat=lat,
                    from_lon=lon,
                    to_lat=to_lat,
                    to_lon=to_lon,
                    directions_response=directions_response
                ).save()

                return directions_response
            else:
                return None

    @staticmethod
    def get_my_applications(user):
        
        applications = JobApplication.objects.filter(
            job__job_state=JobState.pending,
            worker_id=user.id,
            job__archived=False).exclude(
                job__worked_times__worker_id=user.id
            ).distinct()

        return [application.to_model_view() for application in applications]

    @staticmethod
    def create_application(data, user):
        formatter = FormattingUtil(data=data)
        job_id = formatter.get_value(k_job_id, required=True)
        job = get_object_or_404(Job, id=job_id)
        start_address = formatter.get_address(k_address, required=True)
        no_travel_cost = formatter.get_bool(k_no_travel_cost, required=True)
        address_title = formatter.get_value(k_address_title)
        note = formatter.get_value(k_note)
        distance = formatter.get_value(k_distance)

        if job.selected_workers >= job.max_workers:
            raise ValueError('You were too late!')

        start_address.save()

        if address_title:
            FavoriteAddress(address=start_address, title=address_title, user_id=user.id).save()

        try:
            Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return JobNotFoundException().get_response()

        application = JobApplication(
            job_id=job_id, address=start_address, worker_id=user.id,
            application_state=JobApplicationState.pending, no_travel_cost=no_travel_cost,
            created_at=datetime.datetime.utcnow(), modified_at=datetime.datetime.utcnow(),
            distance=distance, note=note
        )
        JobManager.apply(application)
        
        return application.id

    @staticmethod
    def get_applications_list(job_id=None):
        if job_id:
            job = get_object_or_404(Job, id=job_id)
            applications = JobApplication.objects.filter(job=job)
        else:
            applications = JobApplication.objects.filter(
                application_state=JobApplicationState.pending,
                job__job_state=JobState.pending,
                job__selected_workers__lt=F('job__max_workers'),
                job__archived=False
            ).order_by('job__start_time')

        return applications
