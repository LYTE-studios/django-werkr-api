from django.utils import timezone

import datetime

from apps.exports.managers.export_manager import ExportManager

def create_monthly_exports():
    start, end = ExportManager.get_last_month_period()

    ExportManager.create_active_washers_export(start, end)