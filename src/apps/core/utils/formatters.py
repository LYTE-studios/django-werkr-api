import pytz
from django.utils import timezone
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.core.model_exceptions import DeserializationException
from apps.core.models.geo import Address
from datetime import datetime, time, date



class FormattingUtil:
    data: dict

    def __init__(self, data: dict):
        self.data = data

    def get_value(self, value_key: str, required=False):
        try:
            return self.data[value_key]
        except KeyError:
            if required:
                raise DeserializationException()
            return None

    def get_address(self, value_key: str = "k_address", required=False):
        """
        Throws DeserializationException upon false data
        """

        raw_address = self.get_value(value_key, required=required)

        if raw_address is None:
            return None

        return Address.from_json(raw_address)

    def get_bool(self, value_key: str, required=False):
        boolean = self.get_value(value_key, required=required)

        if boolean is None:
            return None

        return FormattingUtil.to_bool(boolean)

    def get_date(self, value_key: str, required=False):
        timestamp = self.get_value(value_key, required=required)

        if timestamp is None:
            return None

        return FormattingUtil.to_date_time(timestamp)

    def get_email(self, value_key: str = "k_email", required=False):
        email = self.get_value(value_key, required=required)

        if email is None:
            return None

        email = FormattingUtil.to_email(email)

        if email is None:
            raise DeserializationException()

        return email

    def get_group(self, value_key: str = "k_group_name", required=False):
        group_name = self.get_value(value_key, required=required)

        if group_name is None:
            return None

        return FormattingUtil.to_group(group_name)

    def get_time(self, value_key: str, required=False):
        value = self.get_value(value_key, required=required)

        if value is None:
            return None

        return FormattingUtil.to_time(int(value))

    def get_int(self, value_key: str, required=False):
        value = self.get_value(value_key, required=required)

        if value is None:
            return None

        return int(value)

    @staticmethod
    def to_user_timezone(time: timezone.datetime):
        return time.astimezone(pytz.timezone('Europe/Brussels'))

    @staticmethod
    def to_time_interval(time1: timezone.datetime, time2: timezone.datetime):

        time1 = FormattingUtil.to_user_timezone(time1)

        time2 = FormattingUtil.to_user_timezone(time2)

        return '{}:{} - {}:{}'.format(time1.hour, FormattingUtil.format_date_number(time1.minute), time2.hour,
                                      FormattingUtil.format_date_number(time2.minute), )


    @staticmethod
    def to_readable_duration(delta: timezone.timedelta):

        hours = delta.seconds//3600

        minutes = (delta.seconds - (hours * 3600)) // 60

        return '{}:{}'.format(FormattingUtil.format_date_number(hours), FormattingUtil.format_date_number(minutes))


    @staticmethod
    def to_readable_time(date_time: timezone.datetime, use_timezone: bool = True):
        time = date_time

        if use_timezone:
            time = FormattingUtil.to_user_timezone(date_time)

        return '{}:{}'.format(FormattingUtil.format_date_number(time.hour), FormattingUtil.format_date_number(time.minute))

    @staticmethod
    def format_date_number(number):
        _number_formatter = "{:02}"

        return _number_formatter.format(int(number))

    @staticmethod
    def to_date(date: timezone.datetime):

        date = FormattingUtil.to_user_timezone(date)

        return '{}/{}'.format(str(date.day), FormattingUtil.format_date_number(date.month))

    @staticmethod
    def to_full_date(date: timezone.datetime):
        try:
            return '{}/{}/{}'.format(FormattingUtil.format_date_number(date.month), FormattingUtil.format_date_number(date.month), str(date.year))
        except Exception as e:
            return None

    @staticmethod
    def to_day_of_the_week(date: timezone.datetime):
        weekday = date.weekday()
        if weekday == 0:
            return 'Monday'
        if weekday == 1:
            return 'Tuesday'
        if weekday == 2:
            return 'Wednesday'
        if weekday == 3:
            return 'Thursday'
        if weekday == 4:
            return 'Friday'
        if weekday == 5:
            return 'Saturday'
        if weekday == 6:
            return 'Sunday'

        return 'Monday'

    @staticmethod
    def to_time(timestamp):
        try:
            hour = timestamp // 60
            minute = (timestamp - (hour * 60))

            date_time = timezone.time(hour, minute)

            return date_time
        except Exception:
            return None

    @staticmethod
    def to_date_time(timestamp):
        try:
            date_time = timezone.datetime.fromtimestamp(timestamp)
        except Exception:
            return None

        return date_time

    @staticmethod
    def to_timestamp(date_time):
        if date_time is None:
            return None
        if isinstance(date_time, datetime):
            return date_time.timestamp().__round__()
        if isinstance(date_time, time):
            return date_time.minute + (date_time.hour * 60)
        if isinstance(date_time, date):
            return datetime.combine(date_time, datetime.min.time()).timestamp().__round__() 
        return 

    @staticmethod
    def to_group(group_name):
        try:
            group = Group.objects.get(name=group_name)
        except Exception:
            return None

        return group

    @staticmethod
    def to_bool(value):
        if value == 1:
            return True
        if value == 0:
            return False

        if value == u'true':
            return True
        if value == u'false':
            return False

        if value == 'true':
            return True
        if value == 'false':
            return False

        return None

    @staticmethod
    def to_email(value):
        value = value.replace(' ', '')

        try:
            validate_email(value)
        except ValidationError as e:
            raise e
        else:
            return value
