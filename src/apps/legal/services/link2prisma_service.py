import os
import requests
from django.conf import settings
from apps.notifications.managers.notification_manager import NotificationManager


def truncate(value, max_length):
    """Helper function to truncate strings to max length"""
    return str(value)[:max_length] if value else ""


class Link2PrismaService:
    """Service for interacting with the Link2Prisma API for social secretary integration"""

    @staticmethod
    def _make_request(method: str, endpoint: str, data: dict = None):
        """Make an authenticated request to the Link2Prisma API"""
        url = f"{settings.LINK2PRISMA_BASE_URL}/{endpoint}"

        try:
            # Ensure employer ref is within limits
            employer_ref = truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64)

            headers = {
                'Content-Type': 'application/json',
                'Employer': employer_ref
            }

            with open(settings.LINK2PRISMA_PFX_PATH, 'rb') as pfx_file:
                pfx_data = pfx_file.read()

                print(url)
                print(method)
                print(headers)

                response = requests.request(
                    method=method,
                    url=url,
                    json=data if data else None,
                    headers=headers,
                    cert=settings.LINK2PRISMA_PFX_PATH,
                )

            print(response)
            print(response.content)

            if response.ok:
                return response.json() if response.content else None
            
            error_msg = f"Link2Prisma API error: {response.status_code} - {response.text}"
            NotificationManager.notify_admin('Link2Prisma API Error', error_msg)
            raise Exception(error_msg)

        except requests.exceptions.SSLError as e:
            error_msg = f"SSL Certificate error: {str(e)}. Make sure the PFX file is valid."
            NotificationManager.notify_admin('Link2Prisma SSL Error', error_msg)
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}. Check if the Link2Prisma service URL is correct."
            NotificationManager.notify_admin('Link2Prisma Connection Error', error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to make Link2Prisma API request: {str(e)}"
            NotificationManager.notify_admin('Link2Prisma API Error', error_msg)
            raise Exception(error_msg)

    @staticmethod
    def test_connection():
        """Test the connection to the Link2Prisma API"""
        try:
            # Check certificate file exists
            if not os.path.exists(settings.LINK2PRISMA_PFX_PATH):
                raise Exception(f"Certificate file not found at: {settings.LINK2PRISMA_PFX_PATH}")

            # Make a test request to the API
            response = Link2PrismaService._make_request(
                method='GET',
                endpoint='health'  # or any valid test endpoint
            )
            if not response:
                raise Exception("No response from health endpoint")
            return True
        except Exception as e:
            NotificationManager.notify_admin('Link2Prisma Connection Test Failed', str(e))
            raise

    @staticmethod
    def fetch_worker(ssn: str):
        """
        Fetch worker data from Link2Prisma by SSN
        
        Args:
            ssn (str): The worker's social security number

        Returns:
            dict: Worker data from Link2Prisma
            None: If worker not found
        """
        try:
            # First check if worker exists
            exists_response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'workerExists/{truncate(ssn, 64)}'
            )

            if not exists_response or not exists_response.get('WorkerExists'):
                return None

            # Get worker details using their worker number
            response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'worker/{exists_response["WorkerNumber"]}'
            )
            return response
        except Exception as e:
            error_msg = f"Failed to fetch worker data: {str(e)}"
            NotificationManager.notify_admin('Link2Prisma Worker Fetch Error', error_msg)
            return None

    @staticmethod
    def handle_job_approval(job_application):
        """
        Send job data to Link2Prisma when a job application is approved
        """
        try:
            worker = job_application.worker
            job = job_application.job

            # Prepare job data according to Link2Prisma schema
            job_data = {
                "NatureDeclaration": "DimonaIn",
                "ContractType": "Normal",  # Can be mapped based on worker type
                "Email": truncate(worker.email, 255),
                "Name": truncate(worker.last_name, 255),
                "Firstname": truncate(worker.first_name, 255),
                "INSS": truncate(worker.worker_profile.ssn, 64),
                "StartingDate": job.start_time.strftime("%Y%m%d"),
                "EndingDate": job.end_time.strftime("%Y%m%d"),
                "StartingHour": job.start_time.strftime("%Y%m%d%H%M"),
                "EndingHour": job.end_time.strftime("%Y%m%d%H%M"),
                "PlannedHoursNbr": int((job.end_time - job.start_time).total_seconds() / 3600),
                "WorkerType": "STU" if worker.worker_profile.worker_type == "student" else "FLX",
                "EmployerRef": truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64)
            }

            # Send job declaration to Link2Prisma
            response = Link2PrismaService._make_request(
                method='POST',
                endpoint='declarations',
                data=job_data
            )

            return True

        except Exception as e:
            error_msg = f"Failed to send job approval to Link2Prisma: {str(e)}"
            NotificationManager.notify_admin('Link2Prisma Job Approval Error', error_msg)
            return False

    @staticmethod
    def handle_job_cancellation(job_application):
        """
        Cancel job in Link2Prisma when application is denied or job is deleted
        """
        try:
            # Prepare cancellation data
            cancel_data = {
                "NatureDeclaration": "DimonaCancel",
                "DimonaPeriodId": truncate(str(job_application.id), 64),
                "Email": truncate(job_application.worker.email, 255)
            }

            # Send cancellation to Link2Prisma
            response = Link2PrismaService._make_request(
                method='POST',
                endpoint='declarations',
                data=cancel_data
            )

            return True

        except Exception as e:
            error_msg = f"Failed to send job cancellation to Link2Prisma: {str(e)}"
            NotificationManager.notify_admin('Link2Prisma Job Cancellation Error', error_msg)
            return False

    @staticmethod
    def sync_worker_data():
        """
        Synchronize worker data with Link2Prisma.
        This method runs daily at 1 AM to ensure worker data is up to date.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            # Get all active workers
            workers = User.objects.filter(
                is_active=True,
                worker_profile__isnull=False
            ).select_related(
                'worker_profile',
                'worker_profile__worker_address'
            )

            sync_success = True
            for worker in workers:
                try:
                    # Check if worker exists in Link2Prisma
                    worker_exists_response = Link2PrismaService._make_request(
                        method='GET',
                        endpoint=f'workerExists/{truncate(worker.worker_profile.ssn, 64)}'
                    )

                    # Prepare worker data according to Link2Prisma schema
                    worker_data = {
                        "Name": truncate(worker.last_name, 255),
                        "Firstname": truncate(worker.first_name, 255),
                        "INSS": truncate(worker.worker_profile.ssn, 64),
                        "Sex": "M",  # TODO: Add gender field to WorkerProfile
                        "Birthdate": worker.worker_profile.date_of_birth.strftime("%Y%m%d") if worker.worker_profile.date_of_birth else None,
                        "Birthplace": truncate(worker.worker_profile.place_of_birth, 255),
                        "Language": "F",  # TODO: Add language preference to User/WorkerProfile
                        "PayWay": "Transfer",
                        "BankAccount": truncate(worker.worker_profile.iban, 34),  # IBAN max length is 34
                        "EmployerRef": truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64),
                        "address": [{
                            "Startdate": worker.date_joined.strftime("%Y%m%d"),
                            "Street": truncate(worker.worker_profile.worker_address.street_name, 255),
                            "HouseNumber": truncate(worker.worker_profile.worker_address.house_number, 10),
                            "ZIPCode": truncate(worker.worker_profile.worker_address.zip_code, 10),
                            "City": truncate(worker.worker_profile.worker_address.city, 255),
                            "Country": "00150"  # Default to Belgium
                        }] if worker.worker_profile.worker_address else [],
                        "contract": [{
                            "Startdate": worker.date_joined.strftime("%Y%m%d"),
                            "EmploymentStatus": "Employee",
                            "Contract": "Usually",
                            "WorkingTime": "PartTime",
                            "WeekhoursWorker": worker.worker_profile.hours or 0,
                            "WeekhoursEmployer": 38.0,  # Standard Belgian work week
                            "Student": {
                                "Exist": "Y" if worker.worker_profile.worker_type == "student" else "N",
                                "SolidarityContribution": "Y"
                            }
                        }]
                    }

                    if worker_exists_response.get("WorkerExists"):
                        # Update existing worker
                        Link2PrismaService._make_request(
                            method='PUT',
                            endpoint=f'worker/{worker_exists_response.get("WorkerNumber")}',
                            data=worker_data
                        )
                    else:
                        # Create new worker
                        Link2PrismaService._make_request(
                            method='POST',
                            endpoint='worker',
                            data=worker_data
                        )

                except Exception as e:
                    error_msg = f"Failed to sync worker {worker.email}: {str(e)}"
                    NotificationManager.notify_admin('Worker Sync Error', error_msg)
                    sync_success = False
                    continue

            return sync_success

        except Exception as e:
            error_msg = f"Worker sync task failed: {str(e)}"
            NotificationManager.notify_admin('Worker Sync Failed', error_msg)
            return False