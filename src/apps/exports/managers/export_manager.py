import datetime
import io
import os

import pandas as pd
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
from apps.exports.models import ExportFile
from apps.jobs.models import JobApplication
from apps.jobs.models import JobState
from apps.jobs.models import TimeRegistration
from django.core.files import File
from django.utils import timezone


class ExportManager:

    @staticmethod
    def get_last_month_period():
        now = timezone.now()

        start_of_month = now.replace(month=now.month - 1, day=1, hour=0, minute=0)

        end_of_month = start_of_month.replace(month=now.month) - datetime.timedelta(
            minutes=1
        )

        return start_of_month, end_of_month

    @staticmethod
    def _create_excel_from_dataframe(data_frame: pd.DataFrame, name: str):
        data_frame.to_excel(name, sheet_name="export", index=False, engine="xlsxwriter")

    @staticmethod
    def create_time_registations_export(
        start_date: datetime.datetime, end_date: datetime.datetime
    ):

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

            def __init__(
                self,
                ssn: str,
                date: datetime.date,
                name: str,
                first_name: str,
                start_time,
                end_time,
                break_time,
                job_title,
                client,
                kilometres,
            ):
                self.ssn = ssn
                self.date = date
                self.name = name
                self.first_name = first_name
                self.start_time = start_time
                self.end_time = end_time
                self.break_time = break_time
                self.job_title = job_title
                self.client = client
                self.kilometres = kilometres

            def to_dict(self):
                total_time = (
                    datetime.datetime.combine(self.date, self.end_time)
                    - datetime.timedelta(
                        hours=self.start_time.hour, minutes=self.start_time.minute
                    )
                ).time()

                readable_break_time = None

                total = total_time

                if self.break_time is not None:
                    t = datetime.datetime.combine(self.date, total)

                    total = (
                        t
                        - datetime.timedelta(
                            hours=self.break_time.hour, minutes=self.break_time.minute
                        )
                    ).time()
                    readable_break_time = FormattingUtil.to_readable_duration(
                        datetime.timedelta(
                            hours=self.break_time.hour, minutes=self.break_time.minute
                        )
                    )

                start = datetime.datetime.combine(self.date, self.start_time)
                end = datetime.datetime.combine(self.date, self.end_time)

                return {
                    "Name": self.name,
                    "FirstName": self.first_name,
                    "Statute": "Student (STU)",
                    "National Number": self.ssn,
                    "Start": FormattingUtil.to_user_timezone(start).replace(
                        tzinfo=None
                    ),
                    "End": FormattingUtil.to_user_timezone(end).replace(tzinfo=None),
                    "Total Time": total_time,
                    "Breaktime": readable_break_time,
                    "Total Time - Breaktime": total,
                    "Kilometres": self.kilometres,
                    "Expenses": "",
                    "Activity": self.job_title,
                    "Team": self.client,
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

            application = JobApplication.objects.filter(
                worker=registration.werker, job=registration.job
            ).first()

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
                ssn=registration.werker.company_name,
                date=registration.job.start_time.date(),
                name=registration.werker.last_name,
                first_name=registration.werker.first_name,
                start_time=registration.start_time.time(),
                end_time=registration.end_time.time(),
                break_time=registration.break_time,
                job_title=registration.job.title,
                client="{} {}".format(
                    registration.job.customer.first_name,
                    registration.job.customer.last_name,
                ),
                kilometres=kilometres,
            )

            data.append(export)

        registrations_df = pd.DataFrame.from_records([s.to_dict() for s in data])

        file_name = "registrations_monthly_{}.xlsx".format(
            FormattingUtil.to_timestamp(timezone.now())
        )

        ExportManager._create_excel_from_dataframe(registrations_df, file_name)

        bytes = open(file_name, "rb").read()

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception("File not created")

        extra_text = ""

        is_intermediate = start_date.month == datetime.datetime.now().month

        if is_intermediate:
            extra_text = "INTERMEDIATE"

        registrations_export = ExportFile(
            name="Registrations monthly - {} {}".format(
                start_date.strftime("%B"), extra_text
            ),
            file_name=file_name,
            description="A monthly export of all registered time",
            file=file,
        )

        registrations_export.save()

        os.remove(file_name)

    @staticmethod
    def create_active_werkers_export(
        start_date: datetime.datetime, end_date: datetime.datetime
    ):

        werkers = (
            TimeRegistration.objects.filter(
                # Job specific
                job__start_time__range=(start_date, end_date),
                job__job_state=JobState.done,
                job__archived=False,
            )
            .values(k_werker)
            .distinct()
        )

        werkers_df = pd.DataFrame(
            list(
                werkers.values(
                    "werker__first_name",
                    "werker__last_name",
                    "werker__email",
                    "werker__company_name",
                    "werker__phone_number",
                    "werker__date_of_birth",
                    "werker__tax_number",
                    "werker__address__street_name",
                    "werker__address__house_number",
                    "werker__address__box_number",
                    "werker__address__city",
                    "werker__address__zip_code",
                    "werker__address__country",
                ),
            ),
        )

        werkers_df = werkers_df.rename(
            columns={
                "werker__first_name": "FirstName",
                "werker__last_name": "LastName",
                "werker__email": "Email",
                "werker__company_name": "NationalNumber",
                "werker_phone_number": "PhoneNumber",
                "werker__date_of_birth": "BirthDate",
                "werker__tax_number": "Iban",
                "werker__address__street_name": "Street",
                "werker__address__house_number": "HouseNumber",
                "werker__address__box_number": "BoxNumber",
                "werker__address__city": "City",
                "werker__address__zip_code": "PostalCode",
                "werker__address__country": "Country",
            }
        )

        file_name = "werkers_monthly_{}.xlsx".format(
            FormattingUtil.to_timestamp(timezone.now())
        )

        ExportManager._create_excel_from_dataframe(werkers_df, file_name)

        bytes = open(file_name, "rb").read()

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception("File not created")

        werkers_export = ExportFile(
            name="Washers monthly - {}".format(start_date.strftime("%B")),
            file_name=file_name,
            description="A monthly export of all werkers that worked this month",
            file=file,
        )

        werkers_export.save()

        os.remove(file_name)
