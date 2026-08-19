from celery import shared_task
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification
from django.contrib.contenttypes.models import ContentType

User = get_user_model()

@shared_task
def create_admin_notification(notification_type, title, message, app_label, model_name, object_id):
    admins = User.objects.filter(user_type__in=['admin', 'super_admin'], is_active=True)
    
    content_type = None
    if app_label and model_name:
        try:
            content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            pass

    notifications = []
    for admin in admins:
        notifications.append(
            Notification(
                recipient=admin,
                notification_type=notification_type,
                title=title,
                message=message,
                content_type=content_type,
                object_id=object_id
            )
        )
    
    Notification.objects.bulk_create(notifications)
    
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            "admin_notifications",
            {
                "type": "send_notification",
                "notification": {
                    "notification_type": notification_type,
                    "title": title,
                    "message": message,
                    "object_id": object_id
                }
            }
        )
