from django.db import models

from api.settings import AUTH_USER_MODEL
from apps.core.models.geo import Address


class FavoriteAddress(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.PROTECT)

    title = models.CharField(max_length=56, null=True)

    address = models.ForeignKey(Address, on_delete=models.CASCADE)

    def to_model_view(self):
        return self.address.to_model_view()
