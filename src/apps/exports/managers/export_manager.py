import datetime
import os
import io

import pandas as pd
from django.utils import timezone
from django.core.files import File

from core.features.base.util.formatting_util import FormattingUtil
from core.features.base.util.wire_names import *
from core.features.exports.models.export_file import ExportFile
from core.features.jobs.models.applications.job_application import JobApplication
from core.features.jobs.models.states.job_state import JobState
from core.features.jobs.models.time_registrations.time_registration import TimeRegistration


class ExportManager():

    @staticmethod
    def get_last_month_period():
        now = timezone.now()

        start_of_month = now.replace(month=now.month - 1, day=1, hour=0, minute=0)

        end_of_month = start_of_month.replace(month=now.month) - datetime.timedelta(minutes=1)

        return start_of_month, end_of_month


    @staticmethod
    def _create_excel_from_dataframe(data_frame: pd.DataFrame, name: str):
        data_frame.to_excel(name, sheet_name='export', index=False, engine='xlsxwriter')


    @staticmethod
    def create_time_registations_export(start_date: datetime.datetime, end_date: datetime.datetime):

        class TimeRegistrationExport:
            ssn: str
            date: datetime.date
            name: str
            first_name: str
            start_time: datetime.datetime
            end_time: datetime.datetime
            break_time: datetime.time
            job_title: str
            client: str
            kilometres: float

            def __init__(self, ssn: str ,date: datetime.date, name: str, first_name: str, start_time, end_time, break_time, job_title, client, kilometres,):
                self.ssn = ssn
                self.date = date
                self.name = name
                self.first_name = first_name
                self.start_time = start_time
                self.end_time = end_time
                self.break_time =  break_time
                self.job_title = job_title
                self.client = client
                self.kilometres = kilometres

            def to_dict(self):
                total_time = (datetime.datetime.combine(self.date, self.end_time) - datetime.timedelta(hours=self.start_time.hour, minutes=self.start_time.minute)).time()

                readable_break_time = None

                total = total_time

                if self.break_time is not None:
                    t = datetime.datetime.combine(self.date, total)

                    total = (t - datetime.timedelta(hours=self.break_time.hour, minutes=self.break_time.minute)).time()
                    readable_break_time = FormattingUtil.to_readable_duration(datetime.timedelta(hours=self.break_time.hour, minutes=self.break_time.minute))

                start = datetime.datetime.combine(self.date, self.start_time)
                end = datetime.datetime.combine(self.date, self.end_time)

                return {
                    'Name': self.name,
                    'FirstName': self.first_name,
                    'Statute': 'Student (STU)',
                    'National Number': self.ssn,
                    'Start': FormattingUtil.to_user_timezone(start).replace(tzinfo=None),
                    'End': FormattingUtil.to_user_timezone(end).replace(tzinfo=None),
                    'Total Time': total_time,
                    'Breaktime': readable_break_time,
                    'Total Time - Breaktime': total,
                    'Kilometres': self.kilometres,
                    'Expenses': '',
                    'Activity': self.job_title,
                    'Team': self.client,
                }


        registrations = TimeRegistration.objects.filter(
            # Job specific
            job__start_time__range=(start_date, end_date),
            job__job_state=JobState.done,
            job__archived=False,
        ).values_list(flat=True)

        data = []

        for id in registrations:

            try:
                registration = TimeRegistration.objects.get(id=id)
            except TimeRegistration.DoesNotExist:
                continue

            application = JobApplication.objects.filter(washer=registration.washer, job=registration.job).first()

            kilometres = 0

            # try:
            #     if lat is not None and lon is not None:
            #         lat = application.address.latitude
            #         lon = application.address.longitude
            #         directions = json.loads(DirectionsView.fetch_directions(lat, lon, application.job.address.latitude, application.job.address.longitude).content)

            #         kilometres = directions["routes"][0]["distanceMeters"] / 1000

            #         application.distance = kilometres

            #         application.save()

            # except Exception as e:
            #     return e

            if application.no_travel_cost is False:
                kilometres = application.distance * 2

            export = TimeRegistrationExport(
                ssn=registration.washer.company_name,
                date=registration.job.start_time.date(),
                name=registration.washer.last_name,
                first_name=registration.washer.first_name,
                start_time=registration.start_time.time(),
                end_time=registration.end_time.time(),
                break_time=registration.break_time,
                job_title=registration.job.title,
                client='{} {}'.format(registration.job.customer.first_name, registration.job.customer.last_name),
                kilometres=kilometres,
            )

            data.append(export)

        registrations_df = pd.DataFrame.from_records([s.to_dict() for s in data])

        file_name = 'registrations_monthly_{}.xlsx'.format(FormattingUtil.to_timestamp(timezone.now()))

        ExportManager._create_excel_from_dataframe(registrations_df, file_name)

        bytes = open(file_name, 'rb').read()

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception('File not created')

        extra_text = ''

        is_intermediate = start_date.month == datetime.datetime.now().month

        if is_intermediate:
            extra_text = 'INTERMEDIATE'

        registrations_export = ExportFile(
            name='Registrations monthly - {} {}'.format(start_date.strftime('%B'), extra_text),
            file_name=file_name,
            description='A monthly export of all registered time',
            file=file,
        )

        registrations_export.save()

        os.remove(file_name)


    @staticmethod
    def create_active_washers_export(start_date: datetime.datetime, end_date: datetime.datetime):

        washers = TimeRegistration.objects.filter(
            # Job specific
            job__start_time__range=(start_date, end_date),
            job__job_state=JobState.done,
            job__archived=False,
        ).values(k_washer).distinct()

        washers_df = pd.DataFrame(list(washers.values(
            'washer__first_name',
            'washer__last_name',
            'washer__email',
            'washer__company_name',
            'washer__phone_number',
            'washer__date_of_birth',
            'washer__tax_number',
            'washer__address__street_name',
            'washer__address__house_number',
            'washer__address__box_number',
            'washer__address__city',
            'washer__address__zip_code',
            'washer__address__country',
        ),),)

        washers_df =  washers_df.rename(columns={
            'washer__first_name': 'FirstName',
            'washer__last_name': 'LastName',
            'washer__email': 'Email',
            'washer__company_name': 'NationalNumber',
            'washer_phone_number': 'PhoneNumber',
            'washer__date_of_birth': "BirthDate",
            'washer__tax_number': 'Iban',
            'washer__address__street_name': 'Street',
            'washer__address__house_number': 'HouseNumber',
            'washer__address__box_number': 'BoxNumber',
            'washer__address__city': 'City',
            'washer__address__zip_code': 'PostalCode',
            'washer__address__country': 'Country',
        })

        file_name = 'washers_monthly_{}.xlsx'.format(FormattingUtil.to_timestamp(timezone.now()))

        ExportManager._create_excel_from_dataframe(washers_df, file_name)

        bytes = open(file_name, 'rb').read()

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception('File not created')

        washers_export = ExportFile(
            name='Washers monthly - {}'.format(start_date.strftime('%B')),
            file_name=file_name,
            description='A monthly export of all washers that worked this month',
            file=file,
        )

        washers_export.save()

        os.remove(file_name)



