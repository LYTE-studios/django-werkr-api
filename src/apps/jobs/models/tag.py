import uuid
from django.db import models
from django.conf import settings


class Tag(models.Model):
    """
    This class represents a tag that can be associated with CustomerProfiles, Jobs, and WorkerProfiles.
    Each tag has a title, color, icon (SVG), and can be associated with a special committee.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=64)
    color = models.CharField(max_length=32)  # Store color as string (e.g., "#FF0000")
    icon = models.TextField()  # Store SVG as string
    special_committee = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def to_model_view(self):
        """
        Returns a dictionary representation of the Tag model.
        """
        return {
            'id': self.id,
            'title': self.title,
            'color': self.color,
            'icon': self.icon,
            'special_committee': self.special_committee,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
        }

    class Meta:
        ordering = ['title']