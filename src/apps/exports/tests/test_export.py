from apps.exports.jobs.monthly_exports import create_monthly_exports
from django.test import TestCase


class ExportTests(TestCase):

    def monthly_export_cron(self):
        create_monthly_exports()
