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
# from api.my_secrets import GOOGLE_BASE_URL, GOOGLE_ROUTES_URL, GOOGLE_API_KEY
from django.shortcuts import get_object_or_404


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
        application = get_object_or_404(JobApplication, id=application_id)
        JobManager.approve_application(application)
        application.job.save()
        application.save()

    @staticmethod
    def deny_application(application_id):
        application = get_object_or_404(JobApplication, id=application_id)
        JobManager.deny_application(application)
        application.job.save()
        application.save()

    @staticmethod
    def fetch_directions(lat, lon, to_lat, to_lon):

        stored_directions = StoredDirections.objects.filter(
            Q(from_lat=lat) & Q(from_lon=lon) & Q(to_lat=to_lat) & Q(to_lon=to_lon)
        ).first()

        if stored_directions and not stored_directions.check_expired():
            return stored_directions.directions_response
        else: 
            response = requests.post(
                url='{}/directions/v2:computeRoutes'.format(GOOGLE_ROUTES_URL),
                headers={
                    "X-Goog-Api-Key": GOOGLE_API_KEY,
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
                directions_response = response.json()

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
        now = datetime.datetime.now()
        approved_applications = JobApplication.objects.filter(worker_id=user.id,
                                                              job__start_time__gt=now,
                                                              job__archived=False,
                                                              application_state=JobApplicationState.approved)[:25]
        applications = JobApplication.objects.filter(
            ~Q(application_state=JobApplicationState.approved),
            worker_id=user.id,
            job__start_time__gt=now,
            job__archived=False)[:50]

        application_model_list = [application.to_model_view() for application in approved_applications]
        for application in applications:
            if application.application_state == JobApplicationState.pending and application.job.selected_workers >= application.job.max_workers:
                continue
            application_model_list.append(application.to_model_view())

        return application_model_list

    @staticmethod
    def create_application(data, user):
        formatter = FormattingUtil(data=data)
        job_id = formatter.get_value(k_job_id, required=True)
        job = get_object_or_404(Job, id=job_id)
        start_address = formatter.get_address(k_address, required=True)
        no_travel_cost = formatter.get_bool(k_no_travel_cost, default=False)
        address_title = formatter.get_value(k_address_title)
        note = formatter.get_value(k_note)
        distance = formatter.get_value(k_distance)

        if job.selected_workers >= job.max_workers:
            raise ValueError('You were too late!')

        start_address.save()
        if address_title:
            FavoriteAddress(address=start_address, title=address_title, user_id=user.id).save()

        if distance is None:
            try:
                distance = JobApplicationService.fetch_directions(
                    lat=start_address.latitude, lon=start_address.longitude,
                    to_lat=job.address.latitude, to_lon=job.address.longitude
                ).json()["routes"][0]["distanceMeters"] / 1000
            except Exception:
                pass

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
