import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """One row per admin action: who did what, to which record, and when."""

    class Action(models.TextChoices):
        # Users
        USER_APPROVED = 'user.approved', 'Approved user'
        USER_REJECTED = 'user.rejected', 'Rejected user'
        USER_DEACTIVATED = 'user.deactivated', 'Deactivated user'
        USER_DELETED = 'user.deleted', 'Deleted user'
        USERS_DELETED_ALL = 'user.deleted_all', 'Deleted all users'
        USER_ROLE_CHANGED = 'user.role_changed', 'Changed user role'
        # Admin accounts
        ADMIN_INVITED = 'admin.invited', 'Invited admin'
        SUPERADMIN_CREATED = 'admin.superadmin_created', 'Created super admin'
        ADMIN_UPDATED = 'admin.updated', 'Edited admin'
        ADMIN_DELETED = 'admin.deleted', 'Deleted admin'
        ADMIN_INVITE_RESENT = 'admin.invite_resent', 'Resent admin invite'
        # Jobs
        JOB_APPROVED = 'job.approved', 'Approved job'
        JOB_UNAPPROVED = 'job.unapproved', 'Unapproved job'
        JOB_REJECTED = 'job.rejected', 'Rejected job'
        JOB_CREATED = 'job.created', 'Created job'
        JOB_UPDATED = 'job.updated', 'Edited job'
        JOB_DELETED = 'job.deleted', 'Deleted job'
        JOB_STATUS_CHANGED = 'job.status_changed', 'Changed job status'
        JOB_FEATURED_TOGGLED = 'job.featured_toggled', 'Changed featured job'
        # Categories
        CATEGORY_CREATED = 'category.created', 'Created category'
        CATEGORY_UPDATED = 'category.updated', 'Edited category'
        CATEGORY_DELETED = 'category.deleted', 'Deleted category'
        # Applications & assignments
        APPLICATION_STATUS_CHANGED = 'application.status_changed', 'Changed application status'
        ASSIGNMENT_CREATED = 'assignment.created', 'Assigned job to worker'
        ASSIGNMENT_UPDATED = 'assignment.updated', 'Edited assignment'
        ASSIGNMENT_DELETED = 'assignment.deleted', 'Removed assignment'
        # Site content
        FOOTER_UPDATED = 'site.footer_updated', 'Edited site footer'
        # The audit trail itself
        AUDIT_LOGS_DELETED = 'audit.deleted', 'Deleted audit log entries'

    class TargetType(models.TextChoices):
        USER = 'user', 'User'
        ADMIN = 'admin', 'Admin'
        JOB = 'job', 'Job'
        CATEGORY = 'category', 'Category'
        APPLICATION = 'application', 'Application'
        ASSIGNMENT = 'assignment', 'Assignment'
        AUDIT_LOG = 'audit_log', 'Audit log'
        SITE = 'site', 'Site settings'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Keep the row (and the snapshot below) if the admin account is later deleted.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs',
    )
    actor_name = models.CharField(max_length=255, blank=True)
    actor_email = models.CharField(max_length=255, blank=True)
    actor_role = models.CharField(max_length=20, blank=True)

    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=20, choices=TargetType.choices, db_index=True)
    # Plain strings, not FKs: the target may be deleted by the very action being logged.
    target_id = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)

    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['actor', '-created_at'])]

    def __str__(self):
        return f"{self.actor_email or 'system'} {self.action} {self.target_label}"
