import os
import requests
import tempfile
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from apps.notifications.managers.notification_manager import NotificationManager
from apps.authentication.models.profiles.worker_profile import WorkerProfile


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

            # Extract certificate and key
            cert_path, key_path = get_cert_and_key(settings.LINK2PRISMA_PFX_PATH)
            
            # For POST/PUT requests with data, send as raw JSON without content-type
            if data and method in ['POST', 'PUT']:
                import json
                # Send as raw data without specifying content-type to let WCF handle it as "Raw"
                headers = {
                    'Employer': employer_ref
                }
                response = requests.request(
                    method=method,
                    url=url,
                    data=json.dumps(data),  # Raw JSON string
                    headers=headers,
                    cert=(cert_path, key_path),
                    verify=True
                )
            else:
                # For GET requests or requests without data
                headers = {
                    'Employer': employer_ref
                }
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    cert=(cert_path, key_path),
                    verify=True
                )

            try:
                print(f"Response status: {response.status_code}")
                print(f"Response headers: {response.headers}")
                print(f"Response content: {response.content}")
                print(f"Response text: {response.text}")
                
                if response.ok:
                    # For POST requests, check if we get a 202 Accepted with UniqueIdentifier
                    if response.status_code == 202:
                        # Link2Prisma returns 202 for async operations
                        if response.content:
                            try:
                                json_response = response.json()
                                # If the JSON response is a string, it's a UniqueIdentifier
                                if isinstance(json_response, str):
                                    return {"UniqueIdentifier": json_response}
                                else:
                                    return json_response
                            except:
                                # If not JSON, return the text as UniqueIdentifier
                                unique_id = response.text.strip().replace('"', '')
                                return {"UniqueIdentifier": unique_id}
                        else:
                            return {"UniqueIdentifier": "no-id"}
                    
                    return response.json() if response.content else None
                
                # Handle 400 status - Link2Prisma returns 400 with UniqueIdentifier for queued operations
                if response.status_code == 400:
                    if response.content:
                        try:
                            # Try to parse as JSON first
                            json_response = response.json()
                            return json_response
                        except:
                            # If not JSON, treat the text as UniqueIdentifier (common for async operations)
                            unique_id = response.text.strip().replace('"', '')
                            return {"UniqueIdentifier": unique_id}
                    return None
                
                # Check for 202 Accepted even if not in response.ok
                if response.status_code == 202:
                    if response.content:
                        try:
                            return response.json()
                        except:
                            # If not JSON, return the text as UniqueIdentifier
                            return {"UniqueIdentifier": response.text.strip()}
                    else:
                        return {"UniqueIdentifier": "no-id"}
                
                # Handle 412 status - Link2Prisma uses this for async operations
                if response.status_code == 412:
                    if response.content:
                        try:
                            # Try to parse as JSON first
                            json_response = response.json()
                            # If it's a worker exists response, return it
                            if 'WorkerExists' in json_response:
                                return json_response
                            # Otherwise treat as UniqueIdentifier
                            return {"UniqueIdentifier": str(json_response)}
                        except:
                            # If not JSON, treat the text as UniqueIdentifier
                            unique_id = response.text.strip().replace('"', '')
                            return {"UniqueIdentifier": unique_id}
                    return None

                error_msg = f"Link2Prisma API error: {response.status_code}"
                details = f"Response: {response.text}"
                print(f"{error_msg} - {details}")
                NotificationManager.notify_admin('Link2Prisma API Error', error_msg[:256])
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
            NotificationManager.notify_admin('Link2Prisma SSL Error', error_msg[:256])
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = "Connection error with Link2Prisma service"
            details = str(e)
            print(f"{error_msg}: {details}")
            NotificationManager.notify_admin('Link2Prisma Connection Error', error_msg[:256])
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Failed to make Link2Prisma API request: {str(e)}"
            print(error_msg)
            NotificationManager.notify_admin('Link2Prisma API Error', error_msg)
            raise Exception(error_msg)

    @staticmethod
    def _dict_to_xml(data: dict, root_tag: str = "worker") -> str:
        """Convert dictionary to XML format for Link2Prisma API"""
        def dict_to_xml_recursive(d, parent_tag=""):
            xml_str = ""
            for key, value in d.items():
                if isinstance(value, dict):
                    xml_str += f"<{key}>{dict_to_xml_recursive(value)}</{key}>"
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml_str += f"<{key}>{dict_to_xml_recursive(item)}</{key}>"
                        else:
                            xml_str += f"<{key}>{item}</{key}>"
                else:
                    # Escape XML special characters
                    if value is not None:
                        value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        xml_str += f"<{key}>{value}</{key}>"
            return xml_str
        
        xml_content = dict_to_xml_recursive(data)
        return f'<?xml version="1.0" encoding="utf-8"?><{root_tag}>{xml_content}</{root_tag}>'

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
        if not ssn:
            return None
        
        try:
            # First check if worker exists
            exists_response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'workerExists/{truncate(ssn, 64)}'
            )

            if not exists_response or not exists_response.get('WorkerExists'):
                return None

            # Get worker details using their worker number
            # Get worker data using correct endpoint format
            response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'worker/{exists_response["WorkerNumber"]}'
            )
            
            # Handle async response (Status 202 returns UniqueIdentifier)
            if isinstance(response, dict) and response.get('UniqueIdentifier'):
                unique_id = response['UniqueIdentifier']
                print(f"Worker data request queued with ID: {unique_id}")
                
                # Check the result after a brief wait
                import time
                time.sleep(2)  # Wait for processing
                
                result = Link2PrismaService._make_request(
                    method='GET',
                    endpoint=f'Result/{unique_id}'
                )
                
                if result and isinstance(result, dict):
                    # Return the worker data from the result
                    return result.get('Response', result)
                else:
                    print(f"Worker data still processing. Queue ID: {unique_id}")
                    return {"status": "processing", "queue_id": unique_id}
            
            return response
        except Exception as e:
            error_msg = "Failed to fetch worker data from Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            NotificationManager.notify_admin('Link2Prisma WorkerFetch Error', error_msg[:256])
            return None

    @staticmethod
    def handle_job_approval(job_application):
        """
        Send Dimona declaration to Link2Prisma when a job application is approved
        """
        try:
            worker = job_application.worker
            job = job_application.job

            if worker.worker_profile.worker_type == WorkerProfile.WorkerType.FREELANCER:
                print("Skipping Dimona declaration for freelancer")
                return True

            # First ensure worker exists in Link2Prisma
            Link2PrismaService.sync_worker(worker)

            # Get worker number from Link2Prisma
            worker_exists_response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'workerExists/{truncate(worker.worker_profile.ssn, 64)}'
            )

            if not worker_exists_response or not worker_exists_response.get('WorkerExists'):
                raise Exception(f"Worker with SSN {worker.worker_profile.ssn} not found in Link2Prisma")

            worker_number = worker_exists_response.get('WorkerNumber')

            # Prepare Dimona data according to Link2Prisma API documentation
            dimona_data = {
                "NatureDeclaration": "DimonaIn",
                "ContractType": "Normal",
                "Email": truncate(worker.email, 255),
                "Name": truncate(worker.last_name, 255),
                "Firstname": truncate(worker.first_name, 255),
                "INSS": truncate(worker.worker_profile.ssn, 64),
                "StartingDate": job.start_time.strftime("%Y%m%d"),
                "EndingDate": job.end_time.strftime("%Y%m%d"),
                "StartingHour": job.start_time.strftime("%H%M"),
                "EndingHour": job.end_time.strftime("%H%M"),
                "PlannedHoursNbr": int((job.end_time - job.start_time).total_seconds() / 3600),
                "WorkerType": "STU" if worker.worker_profile.worker_type == "student" else "FLX",
                "EmployerRef": truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64)
            }

            # Send Dimona declaration using the correct endpoint
            response = Link2PrismaService._make_request(
                method='POST',
                endpoint=f'worker/{worker_number}/dimona',
                data=dimona_data
            )

            if response:
                # Handle both dict and string responses
                if isinstance(response, dict) and response.get('UniqueIdentifier'):
                    unique_id = response['UniqueIdentifier']
                elif isinstance(response, dict) and 'UniqueIdentifier' in response:
                    unique_id = response['UniqueIdentifier']
                else:
                    # Response might be a string UniqueIdentifier directly
                    unique_id = str(response) if response else None
                
                if unique_id:
                    print(f"Dimona declaration submitted with ID: {unique_id}")
                
                # Create Dimona record in local database
                from apps.jobs.models.dimona import Dimona
                from django.utils import timezone
                
                dimona = Dimona.objects.create(
                    id=unique_id,
                    application=job_application,
                    success=None,  # Will be updated when we check the result
                    reason="Dimona declaration submitted to Link2Prisma",
                    created=timezone.now()
                )
                
                return True

            return False

        except Exception as e:
            error_msg = "Failed to send job approval to Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            NotificationManager.notify_admin('Link2Prisma Job Approval Error', error_msg[:256])
            return False

    @staticmethod
    def handle_job_cancellation(job_application):
        """
        Cancel Dimona declaration in Link2Prisma when application is denied or job is deleted
        """
        try:
            # Find the Dimona record for this application
            from apps.jobs.models.dimona import Dimona
            
            dimona = Dimona.objects.filter(application=job_application).first()
            if not dimona:
                print("No Dimona record found for this application")
                return True

            worker = job_application.worker

            # Get worker number from Link2Prisma
            worker_exists_response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'workerExists/{truncate(worker.worker_profile.ssn, 64)}'
            )

            if not worker_exists_response or not worker_exists_response.get('WorkerExists'):
                print(f"Worker with SSN {worker.worker_profile.ssn} not found in Link2Prisma")
                return False

            worker_number = worker_exists_response.get('WorkerNumber')

            # Prepare cancellation data
            cancel_data = {
                "NatureDeclaration": "DimonaCancel",
                "DimonaPeriodId": dimona.id,
                "Email": truncate(worker.email, 255)
            }

            # Send cancellation using the correct endpoint
            response = Link2PrismaService._make_request(
                method='POST',
                endpoint=f'worker/{worker_number}/dimona',
                data=cancel_data
            )

            if response and response.get('UniqueIdentifier'):
                # Update the Dimona record
                dimona.success = False
                dimona.reason = "Dimona declaration cancelled"
                dimona.save()

            return True

        except Exception as e:
            error_msg = "Failed to send job cancellation to Link2Prisma"
            details = str(e)
            print(f"{error_msg}: {details}")
            NotificationManager.notify_admin('Link2Prisma Job Cancellation Error', error_msg[:256])
            return False
        
    
    @staticmethod
    def sync_worker(worker):
        try:
            # Check if worker exists in Link2Prisma
            worker_exists_response = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'workerExists/{truncate(worker.worker_profile.ssn, 64)}'
            )

            # Prepare simplified worker data - complex nested data causes 412 errors
            worker_data = {
                "Name": truncate(worker.last_name, 255),
                "Firstname": truncate(worker.first_name, 255),
                "INSS": truncate(worker.worker_profile.ssn, 64),
                "Sex": "M",  # TODO: Add gender field to WorkerProfile
                "Birthdate": worker.worker_profile.date_of_birth.strftime("%Y%m%d") if worker.worker_profile.date_of_birth else None,
                "Birthplace": truncate(worker.worker_profile.place_of_birth, 255),
                "Language": "F",  # French - TODO: Add language preference to User/WorkerProfile
                "PayWay": "Transfer",
                "BankAccount": truncate(worker.worker_profile.iban, 34),  # IBAN max length is 34
                "EmployerRef": truncate(settings.LINK2PRISMA_EMPLOYER_REF, 64)
            }
            
            # Add address data if available
            if worker.worker_profile.worker_address:
                worker_data["address"] = [{
                    "Startdate": worker.date_joined.strftime("%Y%m%d"),
                    "Street": truncate(worker.worker_profile.worker_address.street_name, 255),
                    "HouseNumber": truncate(worker.worker_profile.worker_address.house_number, 10),
                    "ZIPCode": truncate(worker.worker_profile.worker_address.zip_code, 10),
                    "City": truncate(worker.worker_profile.worker_address.city, 255),
                    "Country": "00150"  # Belgium
                }]
            
            # Add basic contract data
            worker_data["contract"] = [{
                "Startdate": worker.date_joined.strftime("%Y%m%d"),
                "EmploymentStatus": "Employee",
                "Contract": "Usually",
                "WorkingTime": "PartTime" if (worker.worker_profile.hours or 0) < 38 else "FullTime",
                "WeekhoursWorker": float(worker.worker_profile.hours or 20),
                "WeekhoursEmployer": 38.0
            }]
            
            # Add family status (required field)
            worker_data["familystatus"] = [{
                "Startdate": worker.date_joined.strftime("%Y%m%d"),
                "MaritalStatus": "Single",  # Default - TODO: Add to WorkerProfile
                "NumberOfChildren": 0  # Default - TODO: Add to WorkerProfile
            }]

            if worker_exists_response and worker_exists_response.get("WorkerExists") == True:
                # Worker already exists, no need to update
                print(f"Worker already exists with WorkerNumber: {worker_exists_response.get('WorkerNumber')}")
                print("Skipping worker update - using existing worker")
            else:
                # Create new worker and wait for result
                print(f"Creating worker with data: {worker_data}")
                response = Link2PrismaService._make_request(
                    method='POST',
                    endpoint='worker',
                    data=worker_data
                )
                
                print(f"Worker creation response: {response}")
                
                # Get the unique identifier from response
                if response and response.get('UniqueIdentifier'):
                    print(f"Worker creation submitted with ID: {response['UniqueIdentifier']}")
                    # Check result using the identifier
                    result = Link2PrismaService._make_request(
                        method='GET',
                        endpoint=f'Result/{response["UniqueIdentifier"]}'
                    )
                    print(f"Worker creation result: {result}")
                else:
                    print(f"No UniqueIdentifier in response: {response}")

        except Exception as e:
            error_msg = f"Failed to sync worker {truncate(worker.email, 64)}"
            details = str(e)
            print(f"{error_msg}: {details}")
            NotificationManager.notify_admin('Worker Sync Error', error_msg[:256])
        

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
            NotificationManager.notify_admin('Worker Sync Failed', error_msg[:256])
            return False