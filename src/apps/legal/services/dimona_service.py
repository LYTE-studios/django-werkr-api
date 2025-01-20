import requests
from apps.authentication.models.profiles.worker_profile import WorkerProfile
import jwt
import json
from django.contrib.auth import get_user_model
import asyncio
from django.conf import settings

User = get_user_model()

from apps.core.utils.formatters import FormattingUtil

from apps.jobs.models import JobApplication, Job, JobState, TimeRegistration, JobApplicationState, Dimona
import uuid
import datetime
from time import sleep

from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

from apps.notifications.managers.notification_manager import NotificationManager

class DimonaService:

    @staticmethod
    def _get_auth_token():

        url = settings.DIMONA_AUTH_URL

        def get_secure_id():
            return str(uuid.uuid4())

        def get_key():
            cert_str = settings.JWT_SECRET
            key = "\n".join([l.lstrip() for l in cert_str.split("\n")])
            return str(key)

        token = jwt.encode({
            'jti': get_secure_id(),
            'iss': settings.DIMONA_CLIENT_ID,
            'sub': settings.DIMONA_CLIENT_ID,
            'aud': settings.DIMONA_AUTH_URL,
            'exp': FormattingUtil.to_timestamp(datetime.datetime.now() + datetime.timedelta(minutes=5)),
            'nbf': FormattingUtil.to_timestamp(datetime.datetime.now()),
            'iat': FormattingUtil.to_timestamp(datetime.datetime.now()),
        },
            key=get_key(),
            algorithm='RS256',
        )

        response = requests.post(
            url,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'grant_type': 'client_credentials',
                    'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
                    'client_assertion': token,
                }
            )

        if response.status_code == 200:
            return json.loads(response.content)['access_token']


        raise Exception('{}: {} for {}'.format(response.status_code, response.content, '{} -- {}'.format(response.request.headers, response.request.url),))

    @staticmethod
    def _make_post(url: str, data: dict):

        token = DimonaService._get_auth_token()

        return requests.post(url, json=data, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(token),
            },
        )

    @staticmethod
    def _make_get(url: str):

        token = DimonaService._get_auth_token()

        return requests.get(url, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(token),
            },
        )

    @staticmethod
    def format_ssn(ssn: str):
        ssn = ssn.replace('-', '').replace('.', '')

        if(len(ssn) > 11):
            raise Exception('User has an incorrect ssn')

        while(len(ssn) < 11):
            ssn = '0' + ssn

        return ssn

    @staticmethod
    def fetch_employee_data(user: User):
        worker_profile = WorkerProfile.objects.filter(user=user).first()

        if worker_profile.ssn is None:
            raise Exception('User does not have an SSN.')
        
        ssn = DimonaService.format_ssn(worker_profile.ssn)

        if ssn != worker_profile.ssn:
            
            worker_profile.ssn = ssn

            worker_profile.save()

        dimona_data = {
            "employer": settings.EMPLOYER_DATA,
            "worker": {
                "ssin": ssn,
            },
        }

        response = DimonaService._make_post(settings.DIMONA_URL + '/relations/search', dimona_data)

        if response.ok is False:
            raise Exception(response.content)

        json_data = response.json()

        employee_data = json_data['items'][0]['worker']

        return employee_data

    @staticmethod
    def cancel_dimona(application: JobApplication):

        dimona = Dimona.objects.filter(application_id=application.id).first()

        if not dimona:
            return

        dimona_data = {
            "dimonaCancel": {
                "periodId": dimona.id,
            },
        }

        DimonaService._make_post(settings.DIMONA_URL + '/declarations', dimona_data)

        dimona.delete()

    @staticmethod
    def update_dimona(application: JobApplication, registration: TimeRegistration):

        dimona = None

        try:
            dimona = Dimona.objects.filter(application_id=application.id).first()
        except Dimona.DoesNotExist:
            return

        dimona_data = {
            "periodId": int(dimona.id),
            "dimonaUpdate": {
                "plannedHoursNumber": round((registration.end_time - registration.start_time).seconds / 3600),
            },
        }

        token = DimonaService._get_auth_token()

        if token == None:
            raise Exception('No token found')

        DimonaService._make_post(settings.DIMONA_URL + '/declarations', dimona_data)

    @staticmethod
    def get_type_for_user(user: User):
        if user.worker_profile.worker_type == WorkerProfile.WorkerType.FREELANCER:
            return None
        elif user.worker_profile.worker_type == WorkerProfile.WorkerType.STUDENT:
            return 'STU'
        elif user.worker_profile.worker_type == WorkerProfile.WorkerType.FLEXI:
            return 'FLX'

    @staticmethod
    def create_dimona(application: JobApplication):
        employee_type = DimonaService.get_type_for_user(user)

        if employee_type is None:
            return

        if Dimona.objects.filter(application_id=application.id).exists():
            return

        user = application.worker

        ssn = None

        try:
            ssn = DimonaService.format_ssn(user.worker_profile.ssn)
        except Exception as e:
            raise e

        if user.first_name is None or user.last_name is None or ssn is None:
            raise Exception('Worker doesn\'t have enough Data')

        start_time = FormattingUtil.to_user_timezone(application.job.start_time) 
        end_time = FormattingUtil.to_user_timezone(application.job.end_time)  

        dimona_data = {
            "employer": settings.EMPLOYER_DATA,
            "worker": {
                "ssin": ssn,
                "familyName": user.last_name,
                "givenName": user.first_name
            },
            "features": {
                "workerType": employee_type,
            },
            "dimonaIn": {
                "features": {
                    "workerType": employee_type,
                    "jointCommissionNumber": "XXX",
                },
                "plannedHoursNumber": round((end_time - start_time).seconds / 3600),
                "startDate": str(start_time.date()),
                "endDate": str(end_time.date()),
            },
        }

        response = DimonaService._make_post(settings.DIMONA_URL + '/declarations', dimona_data)

        if response.status_code in [200, 201]:
            dimona_id = response.headers['Location'].split('/')[-1]

            if dimona_id is None:
                raise Exception('Dimona not found')

            dimona = Dimona(id=dimona_id, application_id=application.id, created=datetime.datetime.now())

            dimona.save()

            asyncio.create_task(fetch_dimona(id=dimona_id))

            return

        raise Exception('{} {}'.format(response.content, response.request.body))

async def fetch_dimona(id: str, tries = 0):
    sleep(2)

    if tries > 5:
        dimona = Dimona.objects.get(id=id)

        dimona.success = False
        dimona.reason = 'Dimona processing timed out. Contact support.'

        dimona.save()

        NotificationManager.notify_admin('Dimona declaration has failed', dimona.reason)

        raise Exception('Dimona can\'t be fetched')

    search = DimonaService._make_get(settings.DIMONA_URL + '/declarations/{}'.format(id))

    if search.status_code == 404:
        asyncio.create_task(fetch_dimona(id=id, tries=tries+1))
        return

    json_data = search.json()

    dimona = Dimona.objects.get(id=id)


    if json_data['declarationStatus']['result'] == "A":
        dimona.success = True
        dimona.save()

        return

    dimona.success = False
    dimona.reason = json_data['declarationStatus']["anomalies"][0]["label"]["nl"]

    dimona.save()

    NotificationManager.notify_admin('Dimona declaration has failed', dimona.reason)