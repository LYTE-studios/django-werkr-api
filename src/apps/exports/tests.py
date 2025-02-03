

from django.test import TestCase

from core.features.exports.jobs.monthly_exports import create_monthly_exports


class ExportTests(TestCase):

    def monthly_export_cron():
        create_monthly_exports()