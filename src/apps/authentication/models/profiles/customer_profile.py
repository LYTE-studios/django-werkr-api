from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models.geo import Address
from apps.jobs.models.tag import Tag

User = get_user_model()


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    tax_number = models.CharField(max_length=64, null=True)
    company_name = models.CharField(max_length=64, null=True)
    customer_billing_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='customer_billing_address')
    customer_address = models.ForeignKey(Address, null=True, on_delete=models.CASCADE, related_name='customer_address')
    special_committee = models.CharField(max_length=30, null=True)
    tag = models.ForeignKey(Tag, on_delete=models.SET_NULL, null=True, blank=True)