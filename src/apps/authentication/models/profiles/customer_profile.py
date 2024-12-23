from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models.geo import Address

User = get_user_model()


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    tax_number = models.CharField(max_length=64, null=True)
    company_name = models.CharField(max_length=64, null=True)
    customer_billing_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='customer_billing_address')
    customer_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='customer_address')
