from celery import shared_task
from django.contrib.auth import get_user_model
from apps.notifications.managers.notification_manager import NotificationManager
from apps.legal.services.link2prisma_service import Link2PrismaService

User = get_user_model()

@shared_task
def sync_worker_data():
    """
    Daily task to synchronize worker data with Link2Prisma.
    Runs at 1 AM every day.
    """
    try:
        # Initialize counters for reporting
        total_workers = User.objects.filter(
            is_active=True,
            worker_profile__isnull=False
        ).count()
        
        synced_count = 0
        failed_count = 0
        error_messages = []

        # Perform the sync using Link2PrismaService
        if Link2PrismaService.sync_worker_data():
            synced_count = total_workers
        else:
            failed_count = total_workers
            error_messages.append("Link2Prisma sync failed - check admin notifications for details")

        # Send notification with results
        summary = (
            f"Worker Data Sync Summary:\n"
            f"Total Workers: {total_workers}\n"
            f"Successfully Synced: {synced_count}\n"
            f"Failed: {failed_count}\n"
        )
        
        if error_messages:
            summary += "\nErrors:\n" + "\n".join(error_messages)

        NotificationManager.notify_admin(
            'Daily Worker Data Sync Complete',
            summary
        )

        return {
            'status': 'completed',
            'total': total_workers,
            'synced': synced_count,
            'failed': failed_count,
            'errors': error_messages
        }

    except Exception as e:
        error_msg = f"Worker data sync task failed: {str(e)}"
        NotificationManager.notify_admin('Worker Data Sync Failed', error_msg)
        raise  # Re-raise the exception to mark the task as failed