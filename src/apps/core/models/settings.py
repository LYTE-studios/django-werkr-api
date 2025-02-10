from django.db import models


class Settings(models.Model):
    language = models.CharField(max_length=8, null=True)

    @staticmethod
    def get_default():
        return Settings.objects.get(language="en")

    def to_model_view(self):
        return {"language": self.language}
