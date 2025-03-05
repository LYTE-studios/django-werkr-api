from django.apps import AppConfig

class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authentication'

    def ready(self):
        def create_groups():
            from apps.core.assumptions import CUSTOMERS_GROUP_NAME, CMS_GROUP_NAME, WORKERS_GROUP_NAME
            from django.contrib.auth.models import Group
            from django.conf import settings
            from .models.custom_group import CustomGroup

            group, updated = Group.objects.update_or_create(name=CUSTOMERS_GROUP_NAME)
            if updated:
                CustomGroup.objects.create(group=group, group_secret=settings.CUSTOMER_GROUP_SECRET)
            
            group, updated = Group.objects.update_or_create(name=WORKERS_GROUP_NAME)
            if updated:
                CustomGroup.objects.create(group=group, group_secret=settings.WORKER_GROUP_SECRET)
            
            group, updated = Group.objects.update_or_create(name=CMS_GROUP_NAME)
            if updated:
                CustomGroup.objects.create(group=group, group_secret=settings.CMS_GROUP_SECRET)
        
        from asgiref.sync import sync_to_async
        sync_to_async(create_groups)()