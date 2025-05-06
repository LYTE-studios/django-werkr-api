import os
import requests
import tempfile
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from apps.notifications.managers.notification_manager import NotificationManager
from asgiref.sync import async_to_sync


def get_cert_and_key(pfx_path):
    """Extract certificate and private key from PFX file"""
    try:
        # Read PFX file
        with open(pfx_path, 'rb') as pfx_file:
            pfx_data = pfx_file.read()
        
        # Load PFX without password
        private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, None)
        
        # Create temporary files
        cert_temp = tempfile.NamedTemporaryFile(delete=False)
        key_temp = tempfile.NamedTemporaryFile(delete=False)
        
        # Write certificate
        cert_temp.write(certificate.public_bytes(encoding=pkcs12.serialization.Encoding.PEM))
        cert_temp.close()
        
        # Write private key
        key_temp.write(private_key.private_bytes(
            encoding=pkcs12.serialization.Encoding.PEM,
            format=pkcs12.serialization.PrivateFormat.PKCS8,
            encryption_algorithm=pkcs12.serialization.NoEncryption()
        ))
        key_temp.close()
        
        return (cert_temp.name, key_temp.name)
    except Exception as e:
        print(f"Error extracting certificate and key: {str(e)}")
        raise

def truncate(value, max_length):
    """Helper function to truncate strings to max length"""
    return str(value)[:max_length] if value else ""


class Link2PrismaService:
    """Service for interacting with the Link2Prisma API for social secretary integration"""

    @staticmethod
    def _make_request(method: str, endpoint: str, data: dict = None):
        """Make an authenticated request to the Link2Prisma API"""
        url = f"{settings.LINK2PRISMA_BASE_URL}/{endpoint}"

        print(url)

        try:
            # Ensure employer ref is within limits
            employer_ref = truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64)

            headers = {
                'Content-Type': 'application/json',
                'Employer': employer_ref
            }

            # Extract certificate and key
            cert_path, key_path = get_cert_and_key(settings.LINK2PRISMA_PFX_PATH)
            
            response = requests.request(
                method=method,
                url=url,
                json=data if data else None,
                headers=headers,
                cert=(cert_path, key_path),
                verify=True
            )

            try:
                if response.ok:
                    return response.json() if response.content else None
                
                error_msg = f"Link2Prisma API error: {response.status_code}"
                details = f"Response: {response.text}"
                print(f"{error_msg} - {details}")
                async_to_sync(NotificationManager.notify_admin)('Link2Prisma API Error', error_msg[:256])
                raise Exception(error_msg)
            finally:
                # Clean up temporary files
                try:
                    os.unlink(cert_path)
                    os.unlink(key_path)
                except:
                    pass

        except requests.exceptions.SSLError as e:
            error_msg = "SSL Certificate error"
            details = f"Details: {str(e)}"
            print(f"{error_msg}. {details}")
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma SSL Error', error_msg[:256])
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = "Connection error with Link2Prisma service"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma Connection Error', error_msg[:256])
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to make Link2Prisma API request: {str(e)}"
            print(error_msg)
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma API Error', error_msg)
            raise Exception(error_msg)

    @staticmethod
    def test_connection():
        """Test the connection to the Link2Prisma API"""
        try:
            # Check certificate file exists
            if not os.path.exists(settings.LINK2PRISMA_PFX_PATH):
                raise Exception(f"Certificate file not found at: {settings.LINK2PRISMA_PFX_PATH}")

            # Make a test request to the API
            # Use workerExists endpoint which is synchronous
            response = Link2PrismaService._make_request(
                method='GET',
                endpoint='workerExists/00000000000'  # Test with a dummy SSN
            )
            # If we get a response (even if worker doesn't exist), the connection works
            return isinstance(response, dict)
        except Exception as e:
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma Connection Test Failed', str(e))
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
            # Get current date for worker endpoint
            from datetime import datetime
            today = datetime.now().strftime("%Y%m%d")
            
            response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'worker/{exists_response["WorkerNumber"]}/{today}/{today}'
            )
            return response
        except Exception as e:
            error_msg = "Failed to fetch worker data from Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma Worker Fetch Error', error_msg[:256])
            return None

    @staticmethod
    def handle_job_approval(job_application):
        """
        Send job data to Link2Prisma when a job application is approved
        """
        try:
            worker = job_application.worker

            Link2PrismaService.sync_worker(worker)

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

            return response.status_code == 200

        except Exception as e:
            error_msg = "Failed to send job approval to Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma Job Approval Error', error_msg[:256])
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
            error_msg = "Failed to send job cancellation to Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Link2Prisma Job Cancellation Error', error_msg[:256])
            return False
        
    
    @staticmethod
    def sync_worker(worker):
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

            if worker_exists_response.get("WorkerExists") == True:
                # Update existing worker
                response = Link2PrismaService._make_request(
                    method='PUT',
                    endpoint=f'worker/{worker_exists_response.get("WorkerNumber")}',
                    data=worker_data
                )

                print(response)
            else:
                # Create new worker and wait for result
                response = Link2PrismaService._make_request(
                    method='POST',
                    endpoint='worker',
                    data=worker_data
                )
                
                # Get the unique identifier from response
                if response and response.get('UniqueIdentifier'):
                    # Check result using the identifier
                    result = Link2PrismaService._make_request(
                        method='GET',
                        endpoint=f'Result/{response["UniqueIdentifier"]}'
                    )
                    print(f"Worker creation result: {result}")

        except Exception as e:
            error_msg = f"Failed to sync worker {truncate(worker.email, 64)}"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Worker Sync Error', error_msg[:256])
        

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
                    Link2PrismaService.sync_worker(worker)
                except Exception as e:
                    sync_success = False
                    pass

            return sync_success

        except Exception as e:
            error_msg = "Worker sync task failed"
            details = str(e)
            print(f"{error_msg}: {details}")
            async_to_sync(NotificationManager.notify_admin)('Worker Sync Failed', error_msg[:256])
            return False