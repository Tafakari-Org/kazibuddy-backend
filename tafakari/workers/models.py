from django.db import models
from django.utils import timezone

from skills.models import Skill
from accounts.models import CustomUser
import uuid


class WorkerSkill(models.Model):
    EXPERIENCE_LEVELS = [
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS, default='intermediate')
    years_experience = models.PositiveIntegerField(default=0)
    is_certified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
            unique_together = ('user', 'skill')
