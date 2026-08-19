from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JobApplication
from notifications.tasks import create_admin_notification

@receiver(post_save, sender=JobApplication)
def notify_admins_new_application(sender, instance, created, **kwargs):
    if created:
        title = f"New Application: {instance.job.title}"
        message = f"Worker {instance.worker.email} has applied for {instance.job.title}."
        
        # Dispatch Celery task
        create_admin_notification.delay(
            notification_type='application_submitted',
            title=title,
            message=message,
            app_label='applications',
            model_name='jobapplication',
            object_id=str(instance.id)
        )
