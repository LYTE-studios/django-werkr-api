from click import File
from django.utils import timezone
import io
import os

import pandas as pd

from apps.core.utils.formatters import FormattingUtil
from apps.jobs.models.application import JobApplication
from apps.jobs.models.job_state import JobState
from apps.jobs.models.time_registration import TimeRegistration
from apps.core.models.export_file import ExportFile


class ExportManager:

    @staticmethod
    def get_last_month_period():
        now = timezone.now()

        month_count = now.month - 1

        year = now.year

        if month_count <= 0:
            year = year - 1
            month_count = 12 + month_count

        start_of_month = now.replace(
            year=year, month=month_count, day=1, hour=0, minute=0
        )

        end_of_month = start_of_month.replace(
            year=now.year, month=now.month
        ) - timezone.timedelta(minutes=1)

        return start_of_month, end_of_month

    @staticmethod
    def _create_excel_from_dataframe(data_frame: pd.DataFrame, name: str):
        data_frame.to_excel(name, sheet_name="export", index=False, engine="xlsxwriter")

    @staticmethod
    def create_time_registations_export(
        start_date: timezone.datetime, end_date: timezone.datetime
    ):

        class TimeRegistrationExport:
            ssn: str
            date: timezone.date
            name: str
            first_name: str
            start_time: timezone.datetime
            end_time: timezone.datetime
            break_time: timezone.time
            job_title: str
            client: str
            kilometres: float

            def __init__(
                self,
                ssn: str,
                date: timezone.date,
                name: str,
                first_name: str,
                start_time,
                end_time,
                break_time,
                job_title,
                client,
                kilometres,
                worker_type,
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
                self.worker_type = worker_type

            def to_dict(self):
                total_time = (
                    timezone.datetime.combine(self.date, self.end_time)
                    - timezone.timedelta(
                        hours=self.start_time.hour, minutes=self.start_time.minute
                    )
                ).time()

                readable_break_time = None

                total = total_time

                if self.break_time is not None:
                    t = timezone.datetime.combine(self.date, total)

                    total = (
                        t
                        - timezone.timedelta(
                            hours=self.break_time.hour, minutes=self.break_time.minute
                        )
                    ).time()
                    readable_break_time = FormattingUtil.to_readable_duration(
                        timezone.timedelta(
                            hours=self.break_time.hour, minutes=self.break_time.minute
                        )
                    )

                start = timezone.datetime.combine(self.date, self.start_time)
                end = timezone.datetime.combine(self.date, self.end_time)

                return {
                    "Name": self.name,
                    "FirstName": self.first_name,
                    "Statute": self.worker_type,
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
                worker=registration.worker, job=registration.job
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
                ssn=registration.worker.worker_profile.ssn,
                date=registration.job.start_time.date(),
                name=registration.worker.last_name,
                first_name=registration.worker.first_name,
                start_time=registration.start_time.time(),
                end_time=registration.end_time.time(),
                break_time=registration.break_time,
                job_title=registration.job.title,
                client="{} {}".format(
                    registration.job.customer.first_name,
                    registration.job.customer.last_name,
                ),
                kilometres=kilometres,
                worker_type=registration.worker.worker_profile.worker_type or "STU",
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

        is_intermediate = start_date.month == timezone.datetime.now().month

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
    def create_active_washers_export(
        start_date: timezone.datetime, end_date: timezone.datetime
    ):

        washers = (
            TimeRegistration.objects.filter(
                # Job specific
                job__start_time__range=(start_date, end_date),
                job__job_state=JobState.done,
                job__archived=False,
            )
            .values("worker")
            .distinct()
        )

        washers_df = pd.DataFrame(
            list(
                washers.values(
                    "worker__first_name",
                    "worker__last_name",
                    "worker__email",
                    "worker__worker_profile__ssn",
                    "worker__phone_number",
                    "worker__worker_profile__date_of_birth",
                    "worker__worker_profile__iban",
                    "worker__worker_profile__worker_address__street_name",
                    "worker__worker_profile__worker_address__house_number",
                    "worker__worker_profile__worker_address__box_number",
                    "worker__worker_profile__worker_address__city",
                    "worker__worker_profile__worker_address__zip_code",
                    "worker__worker_profile__worker_address__country",
                ),
            ),
        )

        washers_df = washers_df.rename(
            columns={
                "worker__first_name": "FirstName",
                "worker__last_name": "LastName",
                "worker__email": "Email",
                "worker__worker_profile__ssn": "NationalNumber",
                "worker_phone_number": "PhoneNumber",
                "worker__worker_profile__date_of_birth": "BirthDate",
                "worker__worker_profile__iban": "Iban",
                "worker__worker_profile__worker_address__street_name": "Street",
                "worker__worker_profile__worker_address__house_number": "HouseNumber",
                "worker__worker_profile__worker_address__box_number": "BoxNumber",
                "worker__worker_profile__worker_address__city": "City",
                "worker__worker_profile__worker_address__zip_code": "PostalCode",
                "worker__worker_profile__worker_address__country": "Country",
            }
        )

        file_name = "washers_monthly_{}.xlsx".format(
            FormattingUtil.to_timestamp(timezone.now())
        )

        ExportManager._create_excel_from_dataframe(washers_df, file_name)

        bytes = open(file_name, "rb").read()

        file = File(io.BytesIO(bytes), name=file_name)

        if file is None:
            raise Exception("File not created")

        washers_export = ExportFile(
            name="Washers monthly - {}".format(start_date.strftime("%B")),
            file_name=file_name,
            description="A monthly export of all washers that worked this month",
            file=file,
        )

        washers_export.save()

        os.remove(file_name)
