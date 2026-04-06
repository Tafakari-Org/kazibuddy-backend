from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
import uuid
from workers.models import WorkerProfile
from employers.models import EmployerProfile
from skills.models import Skill
# Signal to keep search_vector in sync with title/description
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector


class JobCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)
    icon_url = models.URLField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Job(models.Model):
    class JobType(models.TextChoices):
        PART_TIME = 'part_time', 'Part Time'
        FULL_TIME = 'full_time', 'Full Time'
        TEMPORARY = 'temporary', 'Temporary'
        CONTRACT = 'contract', 'Contract'

    class UrgencyLevel(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class PaymentType(models.TextChoices):
        HOURLY = 'hourly', 'Hourly'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'
        FIXED = 'fixed', 'Fixed'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        FILLED = 'filled', 'Filled'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    class Visibility(models.TextChoices):
        PUBLIC = 'public', 'Public'
        PRIVATE = 'private', 'Private'
        INVITED_ONLY = 'invited_only', 'Invited Only'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, related_name='jobs')
    category = models.ForeignKey(JobCategory, null=True, on_delete=models.SET_NULL, related_name='jobs')
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255, null=True, blank=True)
    location_text = models.CharField(max_length=255)
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    urgency_level = models.CharField(max_length=10, choices=UrgencyLevel.choices, default=UrgencyLevel.MEDIUM)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_type = models.CharField(max_length=10, choices=PaymentType.choices)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    estimated_hours = models.IntegerField(null=True, blank=True)
    max_applicants = models.IntegerField(default=10)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC)
    admin_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_assigned = models.BooleanField(default=False, null=False, blank=False)
    views_count = models.IntegerField(default=0)
    applications_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    filled_at = models.DateTimeField(null=True, blank=True)

    # Pre-computed search vector — updated via post_save signal below
    # Eliminates the need to compute SearchVector on every query
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            # Most impactful — every search query filters on all three simultaneously
            models.Index(fields=['status', 'admin_approved', 'visibility']),

            # Filter indexes
            models.Index(fields=['job_type']),
            models.Index(fields=['urgency_level']),
            models.Index(fields=['payment_type']),
            models.Index(fields=['budget_min', 'budget_max']),

            # Sorting indexes
            models.Index(fields=['created_at']),
            models.Index(fields=['views_count']),
            models.Index(fields=['applications_count']),

            # GIN index for fast full-text search on the pre-computed vector
            GinIndex(fields=['search_vector']),
        ]

    def __str__(self):
        return self.title





@receiver(post_save, sender=Job)
def update_search_vector(sender, instance, **kwargs):
    """
    Recomputes the search_vector after every save.
    Uses update() to avoid triggering the signal again recursively.
    Weight A = title (more important), Weight B = description
    """
    Job.objects.filter(pk=instance.pk).update(
        search_vector=(
            SearchVector('title', weight='A') +
            SearchVector('description', weight='B')
        )
    )


class JobSkill(models.Model):
    class ExperienceLevel(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'
        EXPERT = 'expert', 'Expert'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='job_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='skill_jobs')
    is_required = models.BooleanField(default=True)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.INTERMEDIATE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'skill')


class JobImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=1000)
    file_name = models.CharField(max_length=255)
    caption = models.CharField(max_length=500, null=True, blank=True)
    is_cover = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job.title} - {self.file_name}"


class JobAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attachments')
    file_url = models.URLField(max_length=1000)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(null=True, blank=True, help_text='File size in bytes')
    file_type = models.CharField(max_length=100, null=True, blank=True, help_text='MIME type')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job.title} - {self.file_name}"