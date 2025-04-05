from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from apps.jobs.models import JobApplication, JobApplicationState
from apps.jobs.services.contract_service import JobApplicationService
import json

class Command(BaseCommand):
    help = 'Recalculates distances for approved job applications from March jobs'

    def handle(self, *args, **options):
        # Get the start and end of March
        current_year = timezone.now().year
        start_date = timezone.make_aware(datetime(current_year, 3, 1))
        end_date = timezone.make_aware(datetime(current_year, 4, 1))

        # Get all approved applications for jobs in March
        applications = JobApplication.objects.filter(
            application_state=JobApplicationState.approved,
            job__start_time__gte=start_date,
            job__start_time__lt=end_date
        )

        self.stdout.write(f"Found {applications.count()} applications to process")

        success_count = 0
        error_count = 0

        for application in applications:
            try:
                # Get the addresses
                job_address = application.job.address
                application_address = application.address

                if job_address and application_address:
                    # Use JobApplicationService to recalculate the distance
                    directions_response = JobApplicationService.fetch_directions(
                        lat=application_address.latitude,
                        lon=application_address.longitude,
                        to_lat=job_address.latitude,
                        to_lon=job_address.longitude
                    )

                    if directions_response:
                        response = json.loads(directions_response)
                        new_distance = (response["routes"][0]["distanceMeters"] / 1000) * 2
                        old_distance = application.distance

                        # Update the distance
                        application.distance = new_distance
                        application.save(update_fields=['distance'])

                        self.stdout.write(
                            f"Updated application {application.id}: "
                            f"Old distance: {old_distance:.2f}km, "
                            f"New distance: {new_distance:.2f}km"
                        )
                        success_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Could not get directions for application {application.id}"
                            )
                        )
                        error_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Missing address information for application {application.id}"
                        )
                    )
                    error_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing application {application.id}: {str(e)}"
                    )
                )
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished processing applications. "
                f"Success: {success_count}, Errors: {error_count}"
            )
        )