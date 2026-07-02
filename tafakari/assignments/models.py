from django.db import models
from django.conf import settings
import uuid
from jobs.models import Job


class Assignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='assignment')
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='worker_assignments')
    employer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employer_assignments')
    worker_started_at = models.DateTimeField(blank=True, null=True)
    worker_completed_at = models.DateTimeField(blank=True, null=True)
    employer_approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['worker']),
        ]

    def __str__(self):
        return f"{self.job.title} → {self.worker.full_name}"


class AssignmentCheckin(models.Model):
    CHECKIN_TYPE_CHOICES = [
        ('start', 'Start'),
        ('break', 'Break'),
        ('resume', 'Resume'),
        ('end', 'End'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='checkins')
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignment_checkins')
    checkin_type = models.CharField(max_length=10, choices=CHECKIN_TYPE_CHOICES)
    location = models.CharField(max_length=255, blank=True, null=True)
    location_text = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    photo_url = models.URLField(max_length=500, blank=True, null=True)
    checkin_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.worker.full_name} — {self.checkin_type} at {self.checkin_time}"


class AssignmentMilestone(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completion_notes = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} — {self.status}"