from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Job
from notifications.tasks import create_admin_notification

@receiver(post_save, sender=Job)
def notify_admins_new_job(sender, instance, created, **kwargs):
    if created:
        title = f"New Job Posted: {instance.title}"
        message = f"Employer {instance.employer.email} has posted a new job."
        
        # Dispatch Celery task
        create_admin_notification.delay(
            notification_type='job_created',
            title=title,
            message=message,
            app_label='jobs',
            model_name='job',
            object_id=str(instance.id)
        )
