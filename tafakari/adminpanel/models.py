import uuid
import secrets
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser


def _default_expires_at():
    """Invite tokens are valid for 72 hours."""
    return timezone.now() + timezone.timedelta(hours=72)


class AdminInvite(models.Model):
    """
    Tracks a one-time invite sent to a new admin account.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The dormant admin user this invite belongs to
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="admin_invite",
    )

    # Audit trail: which super-admin sent the invite
    invited_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invites",
    )

    # Secure random token (URL-safe, 48 bytes → 64 hex chars)
    token = models.CharField(max_length=128, unique=True, db_index=True)

    # Lifecycle flags
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    expires_at = models.DateTimeField(default=_default_expires_at)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Admin Invite"
        verbose_name_plural = "Admin Invites"

    def __str__(self):
        status = "used" if self.used else ("expired" if self.is_expired else "pending")
        return f"Invite for {self.user.email} [{status}]"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """True only when the token can still be consumed."""
        return not self.used and not self.is_expired

    @classmethod
    def generate_token(cls) -> str:
        """Return a cryptographically secure URL-safe token."""
        return secrets.token_urlsafe(48)


class FooterSettings(models.Model):
    """
    Contact details shown in the public site footer. A single row (pk=1),
    edited from the admin Footer page.
    """

    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Footer Settings"
        verbose_name_plural = "Footer Settings"

    def __str__(self):
        return "Footer settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FooterSocialLink(models.Model):
    """A social media profile linked from the footer."""

    class Platform(models.TextChoices):
        FACEBOOK = 'facebook', 'Facebook'
        X = 'x', 'X (Twitter)'
        INSTAGRAM = 'instagram', 'Instagram'
        LINKEDIN = 'linkedin', 'LinkedIn'
        YOUTUBE = 'youtube', 'YouTube'
        TIKTOK = 'tiktok', 'TikTok'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    platform = models.CharField(max_length=20, choices=Platform.choices)
    url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.get_platform_display()}: {self.url}"


class FooterCategory(models.Model):
    """A job category featured under "Popular Categories" in the footer."""

    class Icon(models.TextChoices):
        BRIEFCASE = 'briefcase', 'Briefcase'
        SHIELD = 'shield', 'Shield'
        HOME = 'home', 'Home'
        WRENCH = 'wrench', 'Wrench'
        CAR = 'car', 'Car'
        USERS = 'users', 'People'
        HAMMER = 'hammer', 'Hammer'
        SPARKLES = 'sparkles', 'Sparkles'
        BUILDING = 'building', 'Building'
        UTENSILS = 'utensils', 'Utensils'

    category = models.OneToOneField(
        'jobs.JobCategory',
        on_delete=models.CASCADE,
        related_name='footer_entry',
    )
    icon = models.CharField(max_length=20, choices=Icon.choices, default=Icon.BRIEFCASE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "Footer Categories"

    def __str__(self):
        return self.category.name
