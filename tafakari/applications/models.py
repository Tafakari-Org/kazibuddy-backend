from django.db import models
from django.conf import settings
import uuid
from jobs.models import Job

# Create your models here.
class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shortlisted', 'Shortlisted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cover_letter = models.TextField(blank=True, null=True)
    proposed_rate = models.DecimalField(max_digits=10, decimal_places=2)
    availability_start = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    employer_notes = models.TextField(blank=True, null=True)
    worker_notes = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    responded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('job', 'worker')


class WorkerInvitation(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='worker_invitations')
    employer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employer_invitations')
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)