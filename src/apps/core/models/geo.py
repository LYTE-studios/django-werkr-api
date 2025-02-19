from django.db import models
from rest_framework.exceptions import *
from apps.core.utils.wire_names import *


class Address(models.Model):
    """
    Generic model for creating addresses.
    """
    id = models.BigAutoField(primary_key=True, auto_created=True)

    street_name = models.CharField(max_length=256, null=True)
    house_number = models.CharField(max_length=8, null=True)
    box_number = models.CharField(max_length=8, null=True)
    city = models.CharField(max_length=128, null=True)
    zip_code = models.CharField(max_length=16, null=True)
    country = models.CharField(max_length=64, null=True)

    # REQUIRED FIELDS
    # NOTE: They're set to not nullable, to make sure geolocation never trips out.
    latitude = models.FloatField(max_length=16, null=True)
    longitude = models.FloatField(max_length=16, null=True)

    def to_city(self):

        if self.city is not None:
            return self.city

        if self.country is not None:
            return self.country

        return 'Belgium'

    def to_readable(self):
        readable = ''

        if self.street_name is not None:
            readable += '{} '.format(self.street_name)

        if self.house_number is not None:
            readable += '{} '.format(self.house_number)

        if self.zip_code is not None:
            readable += '{} '.format(self.zip_code)

        if self.city is not None:
            readable += '{} '.format(self.city)

        if readable == '':
            return 'Unknown'

        return readable

    def to_model_view(self):
        """
        Creates a dict representation of the model.
        """

        return {
            k_street_name: self.street_name,
            k_house_number: self.house_number,
            k_box_number: self.box_number,
            k_city: self.city,
            k_zip_code: self.zip_code,
            k_country: self.country,
            k_latitude: self.latitude,
            k_longitude: self.longitude,
        }

    @staticmethod
    def from_json(data: dict):
        """
        Creates the Address model from dict input.

        Required fields throw a DeserializationException.
        """

        # Required fields
        try:

            latitude = data[k_latitude]
            longitude = data[k_longitude]

        except KeyError as e:
            # Throw an error upon finding a wrong key.
            raise APIException(e.args)

        # Optional fields
        street_name = None
        house_number = None
        zip_code = None
        city = None
        country = None

        try:

            street_name = data[k_street_name]
            house_number = data[k_house_number]
            zip_code = data[k_zip_code]
            city = data[k_city]
            country = data[k_country]

        except KeyError:
            # Pass not found keys on optional fields
            pass

        # Create model from validated fields
        return Address(street_name=street_name, house_number=house_number, zip_code=zip_code, city=city,
                       country=country, latitude=latitude, longitude=longitude)
