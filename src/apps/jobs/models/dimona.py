from django.db import models

from apps.core.utils.wire_names import *
from .application import JobApplication


class Dimona(models.Model): 
      
    """
    This class stores information related to a job application, including the success status, reason for success,
    and timestamps of the creation. It also provides a method to represent the instance as a dictionary.

    Each static method is documented with its purpose, paramaters and returns values.
    """
    
    id = models.CharField(primary_key=True, null=False, max_length=64)  # Increased to handle Link2Prisma UniqueIdentifiers

    application = models.ForeignKey(JobApplication, on_delete=models.PROTECT, default=None)

    success = models.BooleanField(null=True)

    reason = models.CharField(max_length=256, null=True)

    created = models.DateTimeField(null=True)


    def to_model_view(self):

        """
        Converts the Dimona instance into a dictionnary representation.

        Args:
        self (Dimona): Instance of Dimona model.

        Returns:
        Dictionnary of key-value pairs representing the attributes
        of the Dimona instance.
        """

        return {
            k_id: self.id,
            k_application: self.application.to_model_view(),
            k_success: self.success,
            k_description: self.reason,
            k_created_at: self.created,
        }